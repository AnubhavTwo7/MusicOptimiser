# scripts/setup.ps1
Write-Host "🎵 Setting up Music Playlist Optimizer..." -ForegroundColor Green

# Check Python version
try {
    $pythonVersion = python --version 2>$null
    if (-not $pythonVersion) {
        $pythonVersion = python3 --version 2>$null
    }
    
    if (-not $pythonVersion) {
        Write-Host "❌ Python is not installed or not in PATH" -ForegroundColor Red
        Write-Host "Please install Python 3.9+ from https://python.org" -ForegroundColor Yellow
        exit 1
    }
    
    $versionNumber = ($pythonVersion -split " ")[1]
    $majorMinor = ($versionNumber -split "\.")[0..1] -join "."
    
    if ([version]$majorMinor -lt [version]"3.9") {
        Write-Host "❌ Python 3.9 or higher is required. Found: $versionNumber" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Python version check passed: $versionNumber" -ForegroundColor Green
} catch {
    Write-Host "❌ Error checking Python version" -ForegroundColor Red
    exit 1
}

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
try {
    & "venv\Scripts\Activate.ps1"
} catch {
    Write-Host "❌ Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "You may need to run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
    exit 1
}

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install requirements
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install requirements" -ForegroundColor Red
    exit 1
}

# Create .env file
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "⚠️  Please update .env file with your API keys and configuration" -ForegroundColor Yellow
    } else {
        Write-Host "⚠️  .env.example not found. Creating basic .env file..." -ForegroundColor Yellow
        @"
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=music_playlist
DB_USER=postgres
DB_PASSWORD=your_db_password

# Redis Configuration  
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# API Keys
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
LASTFM_API_KEY=your_lastfm_api_key
LASTFM_API_SECRET=your_lastfm_api_secret

# Application Configuration
DEBUG=True
SECRET_KEY=your_secret_key_here
LOG_LEVEL=INFO
"@ | Out-File -FilePath ".env" -Encoding UTF8
    }
}

# Create necessary directories
Write-Host "Creating directories..." -ForegroundColor Yellow
$directories = @("logs", "data", "data\models", "data\cache", "src\tests")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created directory: $dir" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "🎉 Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Update .env file with your API keys" -ForegroundColor White
Write-Host "2. Install and start PostgreSQL and Redis" -ForegroundColor White
Write-Host "3. Run database migrations: python scripts/migrate.py" -ForegroundColor White
Write-Host "4. Start the application: python -m src.api.main" -ForegroundColor White
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "- API: http://localhost:8000" -ForegroundColor White
Write-Host "- Documentation: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "For Docker setup: docker-compose up -d" -ForegroundColor Yellow
