"""Exercise the native keypad example and its grid/focus extensions headlessly."""
from pathlib import Path
from unittest import mock
import unittest
from ucl import Runtime, UCLError, parse


class ModernCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.r = Runtime(parse(Path('examples/modern-calculator.ucl').read_text(encoding='utf-8')),
                         output=lambda value: None, diagnostic_fn=lambda message: None)
        self.r.prepare()
        self.r.execute()
        self.addCleanup(self.r.close)

    def click(self, ident): self.r.execute(self.r.handlers[ident])
    def display(self): return self.r.ui.read('display')
    def type_number(self, text): self.r.ui.update('display', text, 'input')

    def test_requested_keypad_flow_and_persistent_highlight(self):
        self.click('one')
        self.click('two')
        self.assertEqual(self.display(), '12')
        self.click('add')
        self.assertEqual(self.display(), '')
        self.assertEqual(self.r.ui.get('history')['text'], '12 +')
        self.assertEqual(self.r.buttons['add']['style']['background'], '#2563eb')
        self.click('seven')
        self.assertEqual(self.display(), '7')
        self.assertEqual(self.r.buttons['add']['style']['background'], '#2563eb')
        self.click('equals')
        self.assertEqual(self.display(), '19')
        self.assertEqual(self.r.ui.get('history')['text'], '12 + 7 =')
        self.assertEqual(self.r.buttons['add']['style']['background'], '#334155')

    def test_physically_typed_values(self):
        self.type_number('12.5')
        self.click('multiply')
        self.type_number('4')
        self.click('equals')
        self.assertEqual(self.display(), '50')

    def test_replace_pending_operator(self):
        self.type_number('9')
        self.click('add')
        self.click('subtract')
        self.assertEqual(self.r.ui.get('history')['text'], '9 -')
        self.assertEqual(self.r.buttons['add']['style']['background'], '#334155')
        self.assertEqual(self.r.buttons['subtract']['style']['background'], '#2563eb')
        self.click('four')
        self.click('equals')
        self.assertEqual(self.display(), '5')

    def test_equals_waits_for_second_number(self):
        self.type_number('8')
        self.click('add')
        self.click('equals')
        self.assertEqual(self.display(), '')
        self.assertEqual(self.r.env['calc']['operator'], '+')
        self.assertEqual(self.r.buttons['add']['style']['background'], '#2563eb')

    def test_chaining_is_left_to_right(self):
        self.type_number('12')
        self.click('add')
        self.type_number('3')
        self.click('multiply')
        self.assertEqual(self.r.ui.get('history')['text'], '15 *')
        self.type_number('4')
        self.click('equals')
        self.assertEqual(self.display(), '60')

    def test_new_digit_after_result_starts_fresh(self):
        self.type_number('5')
        self.click('add')
        self.type_number('7')
        self.click('equals')
        self.click('three')
        self.assertEqual(self.display(), '3')
        self.assertEqual(self.r.ui.get('history')['text'], ' ')

    def test_manual_edit_after_result_preserved_when_using_keypad(self):
        self.type_number('5')
        self.click('add')
        self.type_number('7')
        self.click('equals')
        self.type_number('42')
        self.click('three')
        self.assertEqual(self.display(), '423')

    def test_decimal_sign_and_backspace(self):
        self.click('decimal')
        self.click('five')
        self.click('decimal')
        self.assertEqual(self.display(), '0.5')
        self.click('sign')
        self.assertEqual(self.display(), '-0.5')
        self.click('back')
        self.assertEqual(self.display(), '-0.')
        self.click('sign')
        self.assertEqual(self.display(), '0.')

    def test_error_and_typed_recovery(self):
        self.type_number('5')
        self.click('divide')
        self.type_number('0')
        self.click('equals')
        self.assertEqual(self.display(), 'Error')
        self.assertEqual(self.r.ui.get('hint')['text'], 'Cannot divide by zero.')
        self.type_number('6')
        self.click('multiply')
        self.type_number('7')
        self.click('equals')
        self.assertEqual(self.display(), '42')

    def test_invalid_numbers_and_overflow(self):
        for invalid in ('abc', 'nan', 'inf'):
            with self.subTest(invalid=invalid):
                self.click('clear')
                self.type_number(invalid)
                self.click('add')
                self.assertEqual(self.display(), 'Error')
        self.click('clear')
        self.type_number('1e308')
        self.click('multiply')
        self.type_number('1e308')
        self.click('equals')
        self.assertEqual(self.display(), 'Error')

    def test_clear_resets_pending_state(self):
        self.type_number('12')
        self.click('add')
        self.click('clear')
        self.assertEqual(self.display(), '0')
        self.assertEqual(self.r.env['calc']['operator'], '')
        self.assertEqual(self.r.ui.get('history')['text'], ' ')

    def test_keypad_grid_positions_and_spanning_display(self):
        positions = {ident: (row, col, span) for ident,row,col,span in self.r.ui.positions()}
        self.assertEqual(positions['history'], (1, 0, 4))
        self.assertEqual(positions['display'], (2, 0, 4))
        self.assertEqual(positions['seven'], (4, 0, 1))
        self.assertEqual(positions['add'], (6, 3, 1))
        self.assertEqual(positions['zero'], (7, 0, 2))
        self.assertEqual(positions['equals'], (7, 3, 1))

    def test_native_grid_and_focus_dispatch(self):
        tk, window = mock.MagicMock(), mock.MagicMock()
        self.r.populate_desktop(tk, window)
        self.r.widgets['display'].selection_range.assert_called_with(0, 'end')
        self.r.widgets['equals'].grid.assert_called()
        self.assertEqual(window.columnconfigure.call_count, 4)
        self.click('one')
        self.r.widgets['display'].focus_set.assert_called()


class GridExtensionTests(unittest.TestCase):
    def test_browser_grid_css_and_safe_styles(self):
        r = Runtime(parse('[type is browser\nlayout is grid 4 columns\nshow label "Hi" is #hi\nstyle #hi is {"column_span": 4, "align": "right", "border_width": 0}]'))
        r.prepare()
        page = r.page()
        self.assertIn('grid-template-columns:repeat(4', page)
        self.assertIn('grid-column:1/span 4', page)
        self.assertIn('text-align:right', page)
        self.assertIn('border-width:0px', page)

    def test_invalid_grid_styles(self):
        for source in ('layout is grid 0 columns', 'layout is grid 13 columns',
                       'show label "Hi" is #hi\nstyle #hi is {"column_span": 0}',
                       'show label "Hi" is #hi\nstyle #hi is {"align": "url(evil)"}'):
            with self.subTest(source=source), self.assertRaises(UCLError):
                Runtime(parse('[type is gui\n' + source + ']')).prepare()

    def test_captioned_inputs_reserve_a_separate_grid_row(self):
        r = Runtime(parse('[type is gui\nlayout is grid 2 columns\nshow input "Name" is #name\nshow button "Go" is #go\nshow label "Next row" is #next]'))
        r.prepare()
        tk = mock.MagicMock()
        tk.Entry.return_value = mock.Mock()
        tk.Button.return_value = mock.Mock()
        tk.Label.side_effect = lambda *args, **kwargs: mock.Mock()
        r.populate_desktop(tk, mock.Mock())
        self.assertEqual(r.ui.captions['name'].grid.call_args.kwargs['row'], 0)
        self.assertEqual(r.ui.widgets['name'].grid.call_args.kwargs['row'], 1)
        self.assertEqual(r.ui.widgets['go'].grid.call_args.kwargs['row'], 1)
        self.assertEqual(r.ui.widgets['next'].grid.call_args.kwargs['row'], 2)


if __name__ == '__main__': unittest.main()
