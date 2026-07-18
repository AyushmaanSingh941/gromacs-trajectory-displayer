# Contributing

Thanks for contributing to GROMACS Insight Platform.

## Reporting Issues

Before opening a new issue, please check existing reports:

- https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer/issues

When filing a bug, include:

- What you expected
- What happened
- Minimal reproducible input (`.xvg` snippet if possible)
- Python version and OS

## Development Setup

```bash
git clone https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer.git
cd gromacs-trajectory-displayer
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Project Structure

- `app.py`: Streamlit UI
- `src/`: parsing, analysis, statistics, plotting, and reporting modules
- `tests/`: automated tests

## Pull Request Checklist

1. Keep changes focused and well-scoped.
2. Add or update tests for behavior changes.
3. Run tests locally:
   ```bash
   pytest -q
   ```
4. Update documentation when behavior or interfaces change.
5. Use clear commit messages and PR descriptions.

## Coding Guidelines

- Follow PEP 8.
- Prefer clear naming over compact clever code.
- Keep scientific statements accurate and bounded to computed data.
- Avoid introducing unsupported claims in UI or docs.

## License

By contributing, you agree that your contributions are licensed under the MIT License.
