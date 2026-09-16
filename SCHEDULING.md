# Scheduling the report

The reporting command is deliberately scheduler-agnostic. After installing the package, run:

```bash
business-report --data /absolute/path/to/data --output /absolute/path/to/report.html
```

For a daily Linux cron job at 07:00, point cron to the virtual environment's `business-report` executable. In production, send logs to centralized monitoring and alert when the command exits non-zero. For GitHub-based inputs, the same command can run as a scheduled GitHub Action. No scheduler is enabled by this repository itself.
