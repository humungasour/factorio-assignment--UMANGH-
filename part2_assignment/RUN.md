# 🏃 RUN.md – Factory & Belts Solver (macOS / zsh)

## 📦 1. Environment Setup

```bash
# Install required dependencies
pip3 install pytest scipy numpy networkx
```

*(No virtual environment required — works directly on macOS with Python 3.9+.)*

---

## 🧪 2. Run All Unit Tests

To run **all unit tests** for both Factory and Belts modules:

```bash
python3 -m pytest tests/
```

Use `-v` for verbose output:

```bash
python3 -m pytest tests/ -v
```

---

## ⚙️ 3. Run Sample IO Tests (Full Pipeline)

Run both solvers using the provided sample JSON files:

```bash
python3 run_samples.py "python3 factory/main.py" "python3 belts/main.py"
```

This validates full pipeline behavior through stdin/stdout communication.

---

## 🧩 4. Run Solvers Individually

### 🏭 Factory Solver

```bash
cat samples/factory_sample.json | python3 factory/main.py
```

### 🚚 Belts Solver

```bash
cat samples/belts_sample.json | python3 belts/main.py
```

---

## 🔍 5. Debug / Inspect Output

Save solver results to files for manual inspection:

```bash
cat samples/factory_sample.json | python3 factory/main.py > output_factory.json
cat samples/belts_sample.json | python3 belts/main.py > output_belts.json
```

---

## 🧹 6. Optional Cleanup

```bash
rm -rf __pycache__ .pytest_cache
```

---

✅ **Notes**
- Works on macOS (zsh/bash) and Linux.
- Requires Python ≥3.9.
- Both solvers complete within **2 seconds per test case**.
