Get-Process | Select-Object Id,ProcessName | Where-Object { $_.ProcessName -match 'CNEXT|CATIA' }
