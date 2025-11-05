# ESSL Agent Backend - Executable Distribution Guide

## 📋 Table of Contents
1. [Overview](#overview)
2. [Initial Setup](#initial-setup)
3. [Building Executables](#building-executables)
4. [Creating Customer Packages](#creating-customer-packages)
5. [Distribution Workflow](#distribution-workflow)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

### What This Does
Converts your FastAPI application into downloadable executables for Windows, Linux, and macOS that:
- Run without Python installation
- Include all dependencies
- Read configuration from `.env` file
- Start the server automatically

### Key Concepts

#### PyInstaller
- **What it does**: Bundles Python + your code + dependencies into an executable
- **How it works**: Analyzes imports → Collects dependencies → Creates standalone executable
- **Output**: One-folder distribution (executable + _internal folder with libraries)

#### One-Folder vs One-File
- **One-folder** (what we use): Executable + separate _internal folder
  - ✅ Faster startup
  - ✅ Easier to update .env
  - ✅ Smaller executable size
  - ❌ Multiple files to distribute

- **One-file**: Everything in single executable
  - ✅ Single file distribution
  - ❌ Slower startup (extracts to temp on each run)
  - ❌ Harder to manage .env

---

## 🚀 Initial Setup

### Step 1: Copy Files to Your Project

Copy these files to your `essl-agent-backend/` directory:

```bash
cd ~/projects/python/essl-agent-backend/

# Copy the files (you'll create these)
# - launcher.py
# - essl-agent.spec
# - .env.template
# - build.sh
# - package_customer.sh
```

### Step 2: Install PyInstaller

```bash
# Activate your virtual environment if you use one
source .venv/bin/activate

# Install PyInstaller
pip install pyinstaller
```

### Step 3: Make Scripts Executable

```bash
chmod +x build.sh
chmod +x package_customer.sh
```

---

## 🔨 Building Executables

### Understanding the Build Process

```
Source Code → PyInstaller Analysis → Dependency Collection → 
Binary Compilation → Distribution Folder Creation
```

### Build on Current Platform

```bash
# Build for your current OS
./build.sh
```

**What happens:**
1. Checks prerequisites (Python, PyInstaller)
2. Installs dependencies from requirements.txt
3. Cleans previous builds
4. Runs PyInstaller with essl-agent.spec
5. Creates dist/essl-agent/ folder

**Output Structure:**
```
dist/
└── essl-agent/
    ├── essl-agent (or essl-agent.exe on Windows)
    ├── _internal/
    │   ├── (Python runtime)
    │   ├── (all dependencies)
    │   ├── app/
    │   │   ├── main.py
    │   │   ├── core/
    │   │   └── service/
    │   ├── data.json
    │   └── .env.template
    └── (you'll add .env here)
```

### Build for All Platforms

#### Option A: Manual (if you have access to all OS)

**On Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
python -m PyInstaller essl-agent.spec --clean
```

**On Linux:**
```bash
./build.sh
```

**On macOS:**
```bash
./build.sh
```

#### Option B: GitHub Actions (Automated)

1. Create `.github/workflows/` directory:
```bash
mkdir -p .github/workflows
```

2. Copy the GitHub Actions workflow:
```bash
cp .github-workflows-build.yml .github/workflows/build.yml
```

3. Push to GitHub:
```bash
git add .
git commit -m "Add build workflow"
git push
```

4. GitHub automatically builds for all platforms!

5. Download builds from Actions tab → Artifacts

---

## 📦 Creating Customer Packages

### Understanding the Workflow

```
Base Build → Copy for Customer → Add Custom .env → 
Package as Zip → Distribute
```

### Create a Customer Package

```bash
./package_customer.sh "customer-name" "https://server-url.com" "AGENT_ID_123"
```

**Example:**
```bash
./package_customer.sh "acme-corp" "https://api.acme.com" "AGENT_ACME_001"
```

**What happens:**
1. Verifies dist/essl-agent/ exists
2. Creates packages/acme-corp_essl-agent/ folder
3. Copies executable and dependencies
4. Creates custom .env with provided values
5. Adds README.txt with instructions
6. Creates packages/acme-corp_essl-agent.zip

**Output:**
```
packages/
├── acme-corp_essl-agent/
│   ├── essl-agent (executable)
│   ├── _internal/
│   ├── .env (with customer config)
│   └── README.txt
└── acme-corp_essl-agent.zip (ready for download)
```

---

## 🔄 Distribution Workflow

### Full Workflow for Each Customer

```bash
# 1. Build base executable (if not already done)
./build.sh

# 2. Create customer package
./package_customer.sh "customer-name" "https://their-server.com" "THEIR_AGENT_ID"

# 3. Test the package (extract and run)
cd packages/customer-name_essl-agent
./essl-agent  # or double-click on Windows

# 4. Upload to your distribution platform
# - Upload packages/customer-name_essl-agent.zip to cloud storage
# - Or host on your website
# - Or send via email/file transfer

# 5. Send download link to customer
```

### Batch Package Creation

For multiple customers, create a CSV file:

```csv
customer_name,server_url,agent_id
acme-corp,https://api.acme.com,AGENT_001
globex,https://api.globex.com,AGENT_002
initech,https://api.initech.com,AGENT_003
```

Then create a batch script:

```bash
#!/bin/bash
while IFS=, read -r name url agent_id; do
    if [ "$name" != "customer_name" ]; then  # Skip header
        ./package_customer.sh "$name" "$url" "$agent_id"
    fi
done < customers.csv
```

---

## 🧪 Testing

### Test the Executable

```bash
# 1. Extract package
unzip packages/customer-name_essl-agent.zip -d test/

# 2. Navigate to extracted folder
cd test/customer-name_essl-agent/

# 3. Verify .env exists and has correct values
cat .env

# 4. Run the executable
./essl-agent  # or essl-agent.exe on Windows

# 5. Test in browser
curl http://localhost:8000
# or open http://localhost:8000 in browser

# 6. Check logs
# Should see startup messages in console
```

### Common Test Scenarios

1. **Test with default port:**
   ```bash
   # .env has no PORT specified
   # Should start on port 8000
   ```

2. **Test with custom port:**
   ```bash
   # Edit .env, add: PORT=9000
   # Should start on port 9000
   ```

3. **Test without .env:**
   ```bash
   # Rename .env temporarily
   mv .env .env.backup
   # Should show clear error message
   mv .env.backup .env
   ```

---

## 🔧 Troubleshooting

### Build Issues

#### "PyInstaller not found"
```bash
pip install pyinstaller
```

#### "Module not found" during build
Add to `hiddenimports` in `essl-agent.spec`:
```python
hiddenimports=[
    'your.missing.module',
    ...
]
```

#### Build succeeds but executable crashes
Check the build warnings:
```bash
python -m PyInstaller essl-agent.spec --clean 2>&1 | grep -i warning
```

### Runtime Issues

#### "Permission denied" on Linux/Mac
```bash
chmod +x essl-agent
```

#### ".env file not found"
- Ensure .env is in same folder as executable
- Check file permissions: `ls -l .env`

#### "Port already in use"
- Another process is using port 8000
- Add custom port to .env: `PORT=8001`

#### Server starts but can't connect
- Check firewall settings
- Verify SERVER_URL in .env is accessible
- Check logs in console output

### Size Issues

#### Executable is too large (>200MB)
Optimize by excluding unused modules:
```python
# In essl-agent.spec, add to excludes:
excludes=[
    'tkinter',
    'matplotlib',
    'pytest',
    'test',
    'unittest',
],
```

Enable UPX compression:
```python
upx=True,  # In EXE() and COLLECT()
```

---

## 📊 File Size Expectations

- **Windows .exe**: ~80-150 MB
- **Linux binary**: ~70-120 MB  
- **macOS binary**: ~80-130 MB

*Sizes depend on dependencies. FastAPI + uvicorn + httpx creates moderate-sized executables.*

---

## 🎓 Learning Resources

### Understanding PyInstaller
- Official docs: https://pyinstaller.org/
- How it works: https://pyinstaller.org/en/stable/operating-mode.html

### FastAPI in Production
- Deployment guide: https://fastapi.tiangolo.com/deployment/
- Docker vs Executable: https://fastapi.tiangolo.com/deployment/docker/

### Python Packaging
- PEP 517: https://peps.python.org/pep-0517/
- Wheels vs Executables: https://realpython.com/python-wheels/

---

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section
2. Review PyInstaller warnings in build output
3. Test with verbose logging: `uvicorn app.main:app --log-level debug`

---

## 📝 Notes

- **Security**: Don't include sensitive credentials in .env.template
- **Updates**: Rebuild executable when dependencies change
- **Testing**: Always test on target platform before distribution
- **Versioning**: Consider adding version numbers to package names
