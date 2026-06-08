import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mydemo.settings')
sys.path.insert(0, r'd:\ass\mydemo')

import django
django.setup()

from home.tests_algorithms.run_benchmarks import main
main()
