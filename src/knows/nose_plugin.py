import logging
import os
import pprint
import re
import sys
import threading

from collections import defaultdict

import nose
from nose.plugins import Plugin

def parse_test_name(test_name, drop_prefixes):
    try:
        begin = test_name.index('<') + 1
        end = test_name.index('>')
        inside_brackets = test_name[begin:end]
    except ValueError, e:
        return 'SKIPPED - could not figure out name'
    return '.'.join(
        inside_brackets.split(' ', 1)[0].split('.')[drop_prefixes:-1],
    )

class Knows(Plugin):
    name = 'knows'

    def __init__(self, *args, **kwargs):
        self.test_map = defaultdict(set)
        self.output_filehandle = None
        self.output = True
        self.enableOpt = 'with-knows'
        self.test_name = ''

    def options(self, parser, env=os.environ):
        parser.add_option(
            '--knows-file',
            type='string',
            dest='knows_file',
            default='.knows',
            help='Output file for knows plugin.',
        )
        parser.add_option(
            '--knows-out',
            action='store_true',
            dest='knows_out',
            help='Whether to output the mapping of files to unit tests.',
        )
        parser.add_option(
            '--knows-drop-prefixes',
            action='store',
            type='int',
            dest='knows_drop_prefixes',
            default=1,
            help='How many prefixes to drop from the test name.',
        )
        parser.add_option(
            '--knows-dir',
            type='string',
            dest='knows_dir',
            default=os.getcwd(),
            help='Include only this given directory, usually top level project',
        )
        parser.add_option(
            '--knows-exclude',
            type='string',
            dest='knows_exclude',
            default='',
            help='Exclude files from this comma-separated set of directories.',
        )
        super(Knows, self).options(parser, env=env)

    def configure(self, options, config):
        self.enabled = getattr(options, self.enableOpt)
        if self.enabled:
            input_files = config.testNames
            self.drop_prefixes = options.knows_drop_prefixes
            self.knows_dir = options.knows_dir
            self.exclude = []
            if options.knows_exclude:
                self.exclude = ','.split(options.knows_exclude.replace(' ', ''))
            if not options.knows_out:
                if input_files:
                    config.testNames = self.get_tests_to_run(
                        input_files,
                        options.knows_file,
                    )
                self.output = False
            self.output_filename = options.knows_file

        super(Knows, self).configure(options, config)

    def get_tests_to_run(self, input_files, knows_file):
        tests_to_run = []
        match = False
        inputs = set()
        for f in input_files:
            abs_f = os.path.abspath(f)
            if os.path.exists(abs_f) and self.knows_dir in abs_f:
                f = abs_f[len(self.knows_dir) + 1:]
            inputs.add(f)
        with open(knows_file) as fh:
            for line in fh:
                if line.strip(':\n') in inputs:
                    match = True
                elif line.startswith('\t') and match:
                    tests_to_run.append(line.strip())
                else:
                    match = False

        return tests_to_run

    def begin(self):
        if self.output:
            self.output_filehandle = open(self.output_filename, 'w')
            threading.settrace(self.tracer)
            sys.settrace(self.tracer)

    def tracer(self, frame, event, arg):
        filename = frame.f_code.co_filename
        if filename.startswith(self.knows_dir):
            for exclude_dir in self.exclude:
                if filename.startswith(exclude_dir):
                    break
            else:
                if self.test_name:
                    filename = filename[len(self.knows_dir) + 1:]
                    self.test_map[filename].add(self.test_name)

        return self.tracer

    def startTest(self, test):
        self.test_name = parse_test_name(repr(test), self.drop_prefixes)

    def stopTest(self, test):
        pass

    def finalize(self, result):
        if self.output:
            for fname, tests in self.test_map.iteritems():
                self.output_filehandle.write('%s:\n' % (fname,))
                for t in tests:
                    self.output_filehandle.write('\t%s\n' % (t,))

            self.output_filehandle.close()