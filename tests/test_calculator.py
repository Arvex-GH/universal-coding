"""Check the shipped calculator handlers without requiring a graphical display."""
from pathlib import Path
import unittest
from ucl import Runtime, parse


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.output = []
        self.runtime = Runtime(parse(Path('examples/calculator.ucl').read_text(encoding='utf-8')),
                               self.output.append, diagnostic_fn=lambda message: None)
        self.runtime.prepare()
        self.runtime.execute()
        self.addCleanup(self.runtime.close)

    def calculate(self, first, second, button):
        self.runtime.ui.update('first', first, 'input')
        self.runtime.ui.update('second', second, 'input')
        self.runtime.execute(self.runtime.handlers[button])
        return self.runtime.ui.get('result')['text']

    def test_four_operations(self):
        for first, second, button, expected in (
            ('6', '7', 'add', '13'), ('6', '7', 'subtract', '-1'),
            ('6', '7', 'multiply', '42'), ('7', '2', 'divide', '3.5'),
            ('-2.5', '4', 'multiply', '-10'),
        ):
            with self.subTest(button=button):
                self.assertEqual(self.calculate(first, second, button), expected)
        self.assertIn('Result: 42', self.output)

    def test_zero_divisor(self):
        self.assertEqual(self.calculate('5', '0', 'divide'), 'Error')
        self.assertEqual(self.runtime.ui.get('status')['text'], 'Cannot divide by zero.')

    def test_invalid_and_nonfinite_values(self):
        for value in ('', 'hello', 'nan', 'inf', '-inf'):
            with self.subTest(value=value): self.assertEqual(self.calculate(value, '2', 'add'), 'Error')
        self.assertEqual(self.calculate('1e308', '1e308', 'multiply'), 'Error')

    def test_clear_and_recover_after_error(self):
        self.calculate('bad', '2', 'add')
        self.assertEqual(self.calculate('6', '7', 'multiply'), '42')
        self.runtime.execute(self.runtime.handlers['clear'])
        self.assertEqual(self.runtime.ui.get('result')['text'], '0')
        self.assertEqual(self.runtime.ui.read('first'), '')
        self.assertEqual(self.runtime.ui.read('second'), '')
        self.assertEqual(self.runtime.ui.get('status')['style']['color'], 'gray')


if __name__ == '__main__': unittest.main()
