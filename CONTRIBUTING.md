# Contributing

Interested in contributing? Here's how.

## Issues

Found a bug or have a feature request?

1. Check [existing issues](https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer/issues)
2. Open a new issue with:
   - Clear description
   - Steps to reproduce (if bug)
   - Expected vs. actual behavior
   - System info (OS, Python version, file details)

## Code

### Setup

```bash
git clone https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer.git
cd gromacs-trajectory-displayer
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Make changes

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes
3. Test thoroughly
4. Commit with clear message: `git commit -m "Add feature description"`
5. Push: `git push origin feature/your-feature`
6. Open Pull Request

### Code style

- Follow PEP 8
- Max line length: 100 characters
- Use descriptive variable names
- Comment non-obvious logic
- Keep functions focused

### Testing

Before submitting:

- Test with different file sizes (100 frames, 10k frames, 100k+ frames)
- Test different data types (single column, multi-column, non-standard headers)
- Test all chart types and features
- Test error cases (invalid format, corrupted data, empty files)

## License

By contributing, you agree your code is licensed under the MIT License.
