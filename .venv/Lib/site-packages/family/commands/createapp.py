# coding=utf8

import click
import subprocess

@click.command()
@click.argument('project_name')
@click.option('--framework', '-f', default='falcon', help='framework')
def create(framework, project_name):
    cmd = 'paster create -t %s %s' % (framework, project_name)

    p = subprocess.Popen(cmd, shell=True)
    p.communicate()
