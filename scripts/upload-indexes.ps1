$mypath = Split-Path -path $MyInvocation.MyCommand.Path

& "$mypath\algolia.py" upload AW1SEXXQZE cb6bb8cbaa5983b7aa24d42c530c3893 public --file "$mypath\..\public\en\public_index.json" #--clear
#& "$mypath\algolia.py" upload AW1SEXXQZE cb6bb8cbaa5983b7aa24d42c530c3893 public --file "$mypath\..\public\he\public_index.json" --clear
#& "$mypath\algolia.py" upload AW1SEXXQZE cb6bb8cbaa5983b7aa24d42c530c3893 private --file "$mypath\..\public\en\private_index.json" --clear
#& "$mypath\algolia.py" upload AW1SEXXQZE cb6bb8cbaa5983b7aa24d42c530c3893 private --file "$mypath\..\public\he\private_index.json" --clear