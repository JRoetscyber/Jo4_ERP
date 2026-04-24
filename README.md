# JO4 ERP

JO4 ERP is a Flask-based business management system built for coffee shops, cafes, and small food-service operations. It combines point-of-sale workflows, inventory control, recipe costing, transaction history, kitchen order tracking, CSV sales imports, and AI-assisted analytics in one web application.

## Highlights

- Responsive interface for phones, tablets, and desktops
- Inventory management with unit conversion support
- Point of sale with card and cash workflows
- Kitchen display system for active order handling
- Recipe and product cost management
- Historical sales upload from CSV
- Analytics dashboard and demand prediction features
- Multi-user login with per-user data separation
- Docker, Gunicorn, and Cloudflare Tunnel deployment support

## Tech Stack

- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy
- pandas
- scikit-learn
- Gunicorn
- Docker
- Cloudflare Tunnel

## Project Structure

```text
.
|-- app.py
|-- wsgi.py
|-- models.py
|-- predictor.py
|-- routes/
|   |-- api.py
|   |-- auth.py
|   `-- ui.py
|-- templates/
|-- static/
|-- Dockerfile
|-- docker-compose.yml
|-- DEPLOYMENT.md
`-- SECURITY_REVIEW.md
```

## Local Development

1. Create and activate a virtual environment.
2. Install dependencies.
3. Set a `SECRET_KEY`.
4. Run the Flask app.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="replace-me"
python app.py
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="replace-me"
python app.py
```

The development server listens on `http://127.0.0.1:5053`.

## Production Deployment

This repository includes:

- `wsgi.py` for WSGI entry
- `gunicorn.conf.py` for production serving
- `Dockerfile` for container builds
- `docker-compose.yml` for app and Cloudflare Tunnel services
- `.env.example` for runtime configuration

Start the production stack with:

```bash
cp .env.example .env
docker compose up -d --build
```

Deployment details are documented in [DEPLOYMENT.md](DEPLOYMENT.md).

## Security

Recent hardening included:

- CSRF protection for forms and state-changing API requests
- secure session and remember-cookie settings
- proxy-aware production configuration
- upload size limits
- validation fixes in stock and checkout flows

See [SECURITY_REVIEW.md](SECURITY_REVIEW.md) for the full review.

## License

This project is licensed under the [MIT License](LICENSE).
