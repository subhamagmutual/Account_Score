# Testing TIER 2 & TIER 3

Complete checklist to verify TIER 2 (CI/CD, Docs, Structure) and TIER 3 (Makefile, Pre-commit) are working.

---

## **TIER 2: CI/CD, Folder Structure & Documentation**

### **1. Folder Structure Verification**

```bash
# Check all required folders exist
ls -la src/account_score/
ls -la tests/
ls -la config/
ls -la docs/
ls -la docs/api/
ls -la docs/deployment/
ls -la docs/data-governance/
ls -la docs/history/
ls -la scripts/
ls -la models/
ls -la logs/
ls -la .github/workflows/
```

**Expected Result:**
- ✓ All folders present
- ✓ No legacy folders (Account_Score_Enhanced, old_PSL_2025)
- ✓ Only clean, production-ready structure

---

### **2. Source Code Organization**

```bash
# Verify src/account_score/ has all modules
ls -1 src/account_score/ | grep -E "\.py$"
```

**Expected Result:** 15 Python files including:
- ✓ `binner.py`, `scorer.py`, `pipeline.py`
- ✓ `config_validator.py`, `input_validator.py`, `score_validator.py`
- ✓ All utility modules

---

### **3. Documentation Completeness**

```bash
# Check all docs files exist
ls -la docs/api/API_REFERENCE.md
ls -la docs/deployment/DEPLOYMENT_CHECKLIST.md
ls -la docs/data-governance/DATA_DICTIONARY.md
ls -la docs/data-governance/DATA_LINEAGE.md
ls -la docs/history/TIER1_IMPLEMENTATION_SUMMARY.md
```

**Expected Result:**
- ✓ All 5 documentation files present
- ✓ Each file has meaningful content (>1000 bytes)

---

### **4. Configuration Files**

```bash
# Verify all config files exist
ls -la config/
ls -la pyproject.toml
ls -la pytest.ini
ls -la .gitignore
```

**Expected Result:**
- ✓ `binning_thresholds.json`
- ✓ `pipeline_params.json`
- ✓ `scoring_weights.json`
- ✓ `specialty_tiers.json`
- ✓ `state_tiers.json`
- ✓ All config files valid JSON

---

### **5. Test Suite Execution**

```bash
# Run all tests
pytest tests/ -v --cov=src.account_score --cov-report=term-missing

# Or use Makefile
make test
```

**Expected Result:**
- ✓ 50+ tests passing
- ✓ Code coverage ≥30%
- ✓ No import errors
- ✓ All test files run successfully

---

### **6. CI/CD Workflows Validation**

```bash
# Check all workflow files exist and are valid YAML
ls -la .github/workflows/
cat .github/workflows/tests.yml | head -20
cat .github/workflows/lint.yml | head -20
cat .github/workflows/build.yml | head -20
```

**Expected Result:**
- ✓ `tests.yml` - pytest automation config
- ✓ `lint.yml` - code quality checks
- ✓ `build.yml` - build & packaging
- ✓ All files are valid YAML

---

### **7. Data Location Configuration**

```bash
# Check DATA_LOCATION.md
cat DATA_LOCATION.md
```

**Expected Result:**
- ✓ File explains data is at `C:\Box\Box\BOX Subhashree Singh\Business\PAS\data\`
- ✓ Contains configuration instructions
- ✓ Instructions are clear and accurate

---

### **8. .gitignore Verification**

```bash
# Check .gitignore excludes build artifacts
cat .gitignore | grep -E "egg-info|pytest_cache|htmlcov|__pycache__"
```

**Expected Result:**
- ✓ Build artifacts excluded (no .egg-info in repo)
- ✓ Cache files excluded
- ✓ Data folder excluded (../PSL_Modeling, old_PSL_2025)

---

## **TIER 3: Makefile & Pre-commit Hooks**

### **1. Makefile Validation**

```bash
# Show available commands
make help
```

**Expected Result:**
```
Available targets:
  install          Install production dependencies
  install-dev      Install with development tools
  test             Run unit tests with coverage
  lint             Run code quality checks
  format           Auto-format code
  clean            Remove build artifacts
  help             Show this help message
```

---

### **2. Makefile Command Testing**

#### **Test: make install**
```bash
# Create virtual environment first (optional)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Test installation
make install
```

**Expected Result:**
- ✓ Dependencies installed without errors
- ✓ Message: "✓ Production dependencies installed"

---

#### **Test: make install-dev**
```bash
make install-dev
```

**Expected Result:**
- ✓ Dev tools installed (pytest, black, isort, flake8, mypy)
- ✓ Message: "✓ Development dependencies installed"

---

#### **Test: make test**
```bash
make test
```

**Expected Result:**
- ✓ Tests run successfully
- ✓ Coverage report generated in `htmlcov/index.html`
- ✓ Message: "✓ Tests complete"

---

#### **Test: make lint**
```bash
make lint
```

**Expected Result:**
- ✓ All linters run (Black, isort, Flake8, mypy)
- ✓ Message: "✓ Lint checks complete"

---

#### **Test: make format**
```bash
make format
```

**Expected Result:**
- ✓ Code formatted with Black
- ✓ Imports sorted with isort
- ✓ Message: "✓ Code formatting complete"

---

#### **Test: make clean**
```bash
make clean
```

**Expected Result:**
- ✓ Build artifacts removed
- ✓ Cache files removed
- ✓ Message: "✓ Cleanup complete"

---

### **3. Pre-commit Hooks Installation & Testing**

#### **Install pre-commit**
```bash
# Install pre-commit tool
pip install pre-commit

# Set up hooks in git
pre-commit install

# Verify installation
pre-commit run --all-files
```

**Expected Result:**
- ✓ `pre-commit` installed
- ✓ Hooks installed in `.git/hooks/`
- ✓ All hooks run successfully

---

#### **Test: Hook Execution**
```bash
# Create a test file with formatting issues
echo "import os,sys
def test(  ):
    pass" > test_formatting.py

# Try to commit (should fail if pre-commit works)
git add test_formatting.py
git commit -m "Test commit"
```

**Expected Result:**
- ✓ Hooks run automatically on commit
- ✓ Black/isort/Flake8 fix formatting issues
- ✓ mypy checks types
- ✓ Commit may be blocked if issues remain

---

#### **Test: All Hooks**
```bash
# Run all hooks on the entire codebase
pre-commit run --all-files
```

**Expected Result:**
- ✓ Black: ✓ passed (or files fixed)
- ✓ isort: ✓ passed (or files fixed)
- ✓ Flake8: ✓ passed (or issues reported)
- ✓ mypy: ✓ passed (or type errors reported)
- ✓ Trailing whitespace: ✓ passed
- ✓ File size checks: ✓ passed

---

### **4. Git Integration Test**

```bash
# Make a small code change
echo "# Test" >> src/account_score/utils.py

# Stage and commit
git add src/account_score/utils.py
git commit -m "Test pre-commit hooks"
```

**Expected Result:**
- ✓ Pre-commit hooks run automatically
- ✓ Code is formatted/checked before commit
- ✓ Commit succeeds if no issues

---

## **Integration Test: Full Workflow**

```bash
# 1. Start fresh
make clean

# 2. Install everything
make install-dev

# 3. Run tests
make test

# 4. Format code
make format

# 5. Run linters
make lint

# 6. Verify pre-commit works
pre-commit run --all-files

# 7. Make a small change
echo "# New code" >> src/account_score/utils.py

# 8. Commit with hooks
git add src/account_score/utils.py
git commit -m "Integration test"

# 9. Clean up
git reset HEAD~1
git checkout src/account_score/utils.py
make clean
```

**Expected Result:**
- ✓ All steps complete without errors
- ✓ Pre-commit hooks enforced
- ✓ Tests pass
- ✓ Code quality maintained

---

## **Verification Checklist**

### **TIER 2 (CI/CD, Structure, Docs)**
- [ ] All 8 folders present (src/account_score, tests, config, docs, etc.)
- [ ] 15 Python modules in src/account_score/
- [ ] 5 documentation files complete
- [ ] 5 config files valid
- [ ] Tests pass (50+ tests)
- [ ] 3 CI/CD workflows present and valid
- [ ] DATA_LOCATION.md explains data structure
- [ ] .gitignore properly configured

### **TIER 3 (Makefile & Pre-commit)**
- [ ] Makefile has 7 targets (install, install-dev, test, lint, format, clean, help)
- [ ] `make help` shows all targets
- [ ] `make install` works
- [ ] `make test` runs successfully
- [ ] `make lint` completes
- [ ] `make format` fixes code
- [ ] `make clean` removes artifacts
- [ ] .pre-commit-config.yaml has 5+ hooks
- [ ] `pre-commit install` succeeds
- [ ] `pre-commit run --all-files` passes

---

## **Troubleshooting**

### **Issue: Tests fail**
```bash
# Check if dependencies installed
pip list | grep pytest

# Install dev dependencies
make install-dev

# Run tests with verbose output
pytest tests/ -v -s
```

### **Issue: Pre-commit not running**
```bash
# Check if installed
pre-commit --version

# Reinstall hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### **Issue: Makefile not found**
```bash
# Verify Makefile exists
ls -la Makefile

# Make sure you're in project root
pwd
```

---

## **Success Criteria**

✅ **TIER 2 Success:**
- All folders present and organized
- All tests pass
- CI/CD workflows configured
- Documentation complete
- No build artifacts in repo

✅ **TIER 3 Success:**
- All Makefile commands work
- Pre-commit hooks installed and running
- Code quality enforced locally
- Developers can use `make test`, `make lint`, `make format`

---

**If all checks pass, TIER 2 & 3 are working correctly! 🎉**
