import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from .language import UCLError, parse, validate, PATTERNS
from .runtime import Runtime
from .native import build, emit_c
from . import __version__


def main():
    parser = argparse.ArgumentParser(prog='ucl', description='Universal Coding Language')
    parser.add_argument('--version', action='version', version=f'UCL {__version__}')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'serve', 'check', 'ast', 'build', 'emit-c'):
        command = commands.add_parser(name)
        command.add_argument('file')
        if name in {'build', 'emit-c'}: command.add_argument('-o', '--output', required=True)
        if name in {'run', 'serve'}:
            command.add_argument('--host', help='override HTTP bind address')
            command.add_argument('--port', type=int, help='override HTTP port')
            command.add_argument('--debug', action='store_true', help='show debug diagnostics on stderr')
            command.add_argument('--trace', action='store_true', help='trace statement names/locations, not values')
            command.add_argument('--log-format', choices=['text', 'json'], default='text')
            command.add_argument('--log-file', help='also append diagnostics to a UTF-8 file')
            command.add_argument('--arg', action='append', default=[], help='program argument, accessed with argument(index)')
            command.add_argument('--step-limit', type=int, help='cooperative execution quota for terminal/GUI actions')
            command.add_argument('--allowed-host', action='append', help='allowed HTTP Host; repeat for more hosts')
            command.add_argument('--auth-token-env', help='environment variable holding a bearer token')
            command.add_argument('--http-threads', type=int, help='bounded Waitress worker count')
            command.add_argument('--max-body', type=int, help='maximum request body bytes')
            command.add_argument('--max-steps', type=int, help='HTTP execution quota per request')
    words = commands.add_parser('words', help='print the machine-readable vocabulary')
    words.add_argument('--details', action='store_true', help='include descriptions and syntax')
    help_parser = commands.add_parser('help', help='offline statement/builtin reference')
    help_parser.add_argument('topic', nargs='?')
    args = parser.parse_args()
    runtime = None
    try:
        if args.command in {'words', 'help'}:
            from .reference import details, COMMANDS, BUILTINS
            if args.command == 'words': print(json.dumps(details() if args.details else PATTERNS, indent=2))
            elif not args.topic:
                print('Statements: ' + ', '.join(COMMANDS) + '\nBuiltins: ' + ', '.join(BUILTINS))
            elif args.topic in COMMANDS:
                print(COMMANDS[args.topic][0] + '\n\n' + COMMANDS[args.topic][1])
            elif args.topic in BUILTINS: print(BUILTINS[args.topic])
            else: raise UCLError(f'unknown help topic: {args.topic}')
            return 0
        nodes = parse(Path(args.file).read_text(encoding='utf-8'))
        types = validate(nodes)
        if args.command == 'ast': print(json.dumps([asdict(n) for n in nodes], indent=2))
        elif args.command == 'check': print(f'{args.file}: syntax and capability checks passed')
        elif args.command == 'emit-c': Path(args.output).write_text(emit_c(nodes), encoding='utf-8')
        elif args.command == 'build': print(build(nodes, args.output))
        elif args.command in {'run', 'serve'}:
            if args.command == 'serve' and not types & {'server', 'browser'}: raise UCLError('ucl serve requires type is server or browser')
            if args.step_limit is not None and args.step_limit < 1: raise UCLError('step-limit must be positive')
            runtime = Runtime(nodes, output=lambda value: print(value, flush=True))
            runtime.arguments = args.arg
            runtime.source_name = str(Path(args.file))
            runtime.log_format, runtime.log_file = args.log_format, args.log_file
            runtime.prepare()
            runtime.debug = runtime.debug or args.debug or args.trace
            runtime.trace = args.trace
            if args.host is not None: runtime.host = args.host
            if args.port is not None:
                if not 0 <= args.port <= 65535: raise UCLError('port must be between 0 and 65535')
                runtime.port = args.port
            overrides = {'allowed_hosts': args.allowed_host, 'auth_token_environment': args.auth_token_env,
                         'threads': args.http_threads, 'max_body_bytes': args.max_body, 'max_steps': args.max_steps}
            if types & {'server', 'browser'}:
                from .http import settings
                runtime.http_settings = settings({**runtime.http_settings, **{k: v for k,v in overrides.items() if v is not None}})
            with runtime.budget(args.step_limit): runtime.run()
        return 0
    except KeyboardInterrupt: return 130
    except (UCLError, OSError, RecursionError) as e:
        if runtime: runtime.log('error', str(e))
        else: print(f'UCL error: {e}', file=sys.stderr)
        return 1
    finally:
        if runtime: runtime.close()


if __name__ == '__main__': sys.exit(main())
