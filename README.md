### Frappe Faker

app that will generate fake data on frappe apps for testing

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app frappe_faker
```

### Configuration

Open **Faker Settings** and choose an AI provider. Supported providers are:

- OpenAI
- Anthropic
- Gemini
- Ollama
- Custom OpenAI-compatible endpoint

For Gemini, paste a Google AI Studio API key into **API Key**. If **Model Name** is left blank,
Frappe Faker uses `gemini-2.5-flash`. **API Endpoint** is optional and should only be set when
you need to override the default Gemini `generateContent` endpoint.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/frappe_faker
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
