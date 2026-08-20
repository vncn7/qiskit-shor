## Run

Build
```bash
docker build -t qiskit-bell .
```
Run on simulator
```bash
docker run --rm qiskit-bell
```

Run on Real IBM hardware (requires `.env` with `IBM_TOKEN=token`):
```bash
docker run --rm -e USE_HARDWARE=true --env-file .env qiskit-bell
```

## Expected output

```
{'00': 512, '11': 512}  # varies each run
```
