#!/bin/bash

python bin/opsbro

python bin\opsbro agent start --one-shot

echo "Analyser RUN"

python bin\opsbro packs overload   global.shinken-enterprise
python bin\opsbro packs parameters set local.shinken-enterprise.enabled True
python bin\opsbro packs parameters set local.shinken-enterprise.file_result "C:\shinken-local-analyzer-payload.json"
python bin\opsbro agent start --one-shot
type C:\shinken-local-analyzer-payload.json



echo "SERVICE RUN"
python -c \"import sys; print(sys.executable)\"

  # CLEAN ALL logs
wevtutil cl System
wevtutil cl Application

python c:/opsbro/bin/opsbro agent windows service-install"

sc start OpsBro || sc qc OpsBro && sc query OpsBro && wevtutil qe Application && wevtutil qe System && type c:\opsbro.log && bad
python -c \"import time; time.sleep(10)\"
python c:/opsbro/bin/opsbro agent info
python c:/opsbro/bin/opsbro collectors state
python c:/opsbro/bin/opsbro monitoring state
python c:/opsbro/bin/opsbro compliance state
python c:/opsbro/bin/opsbro collectors show
sc stop OpsBro