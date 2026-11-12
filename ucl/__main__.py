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
    for name in ('run', 'check', 'ast', 'build', 'emit-c'):
        command = commands.add_parser(name)
        command.add_argument('file')
        if name in {'build', 'emit-c'}: command.add_argument('-o', '--output', required=True)
        if name == 'run':
            command.add_argument('--host', help='override HTTP bind address')
            command.add_argument('--port', type=int, help='override HTTP port')
    commands.add_parser('words', help='print the machine-readable language vocabulary')
    args = parser.parse_args()
    runtime = None
    try:
        if args.command == 'words':
            print(json.dumps(PATTERNS, indent=2))
            return 0
        nodes = parse(Path(args.file).read_text(encoding='utf-8'))
        validate(nodes)
        if args.command == 'ast': print(json.dumps([asdict(n) for n in nodes], indent=2))
        elif args.command == 'check':
            # Parse expressions and check structure/capabilities without executing code
            # or opening databases. Values and references are checked at runtime.
            print(f'{args.file}: syntax and capability checks passed')
        elif args.command == 'emit-c': Path(args.output).write_text(emit_c(nodes), encoding='utf-8')
        elif args.command == 'build': print(build(nodes, args.output))
        elif args.command == 'run':
            runtime = Runtime(nodes)
            runtime.prepare()
            if args.host is not None: runtime.host = args.host
            if args.port is not None:
                if not 0 <= args.port <= 65535: raise UCLError('port must be between 0 and 65535')
                runtime.port = args.port
            runtime.run()
        return 0
    except KeyboardInterrupt: return 130
    except (UCLError, OSError, RecursionError) as e:
        print(f'UCL error: {e}', file=sys.stderr)
        return 1
    finally:
        if runtime: runtime.close()


if __name__ == '__main__': sys.exit(main())
