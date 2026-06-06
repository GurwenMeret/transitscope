# TransitScope — démarrage de tous les services
Write-Host "Démarrage de TransitScope..." -ForegroundColor Cyan

# OTP
Start-Process powershell -ArgumentList "-NoExit", "-Command", "java -Xmx4G -jar otp/otp-shaded-2.8.1.jar --load otp/graphs/montreal"

# API C#
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd api; dotnet run"

# API Python
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".venv\Scripts\Activate.ps1; cd api_python; uvicorn main:app --port 8001 --reload"

# Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "Services démarrés !" -ForegroundColor Green
Write-Host "Frontend : http://localhost:5173" -ForegroundColor Yellow
Write-Host "API C#   : http://localhost:5062" -ForegroundColor Yellow
Write-Host "API Python: http://localhost:8001" -ForegroundColor Yellow
Write-Host "OTP      : http://localhost:8080" -ForegroundColor Yellow