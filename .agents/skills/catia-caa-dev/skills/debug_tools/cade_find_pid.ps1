Get-Process | Where-Object { $_.ProcessName -like '*CNEXT*' -or $_.ProcessName -like '*CATIA*' } | Select-Object Id,ProcessName
