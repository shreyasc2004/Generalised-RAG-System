$ErrorActionPreference = 'Stop'
python "$PSScriptRoot/scripts/setup.py" @args
exit $LASTEXITCODE

