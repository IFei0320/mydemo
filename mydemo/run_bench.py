import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mydemo.settings')

import django
django.setup()

from home.tests_algorithms.run_benchmarks import main
main()
