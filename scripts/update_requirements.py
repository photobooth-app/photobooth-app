import subprocess


cmd = 'pipreqs --ignore "experiments" --encoding utf8 --force'

# returns the exit code in unix
returned_value = subprocess.call(cmd, shell=True)
print('returned value:', returned_value)
