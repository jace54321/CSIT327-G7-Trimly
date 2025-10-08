# Trimly

A haircut reservation system built with Django and Supabase.

## Dependencies Setup

1. Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

   This will install:
   - Django (5.2.7+) - Web framework
   - python-dotenv (1.0.0+) - For loading environment variables
   - psycopg2-binary (2.9.9+) - PostgreSQL adapter
   - supabase (2.0.0+) - Supabase client

3. Run migrations to set up the database:
   ```bash
   cd trimly
   python manage.py migrate
   ```

Note: The project will use SQLite by default for local development. If you need to connect to Supabase, ask for the `.env` file with the database credentials.

4. Navigate to the project directory:
   ```bash
   cd trimly
   ```

5. Create a `.env` file in the `trimly` directory with your database credentials:
   ```
   DB_USER=postgres.thkruwxuxwktiarugphd
   DB_PASSWORD=<your-password>
   DB_HOST=aws-1-ap-southeast-1.pooler.supabase.com
   DB_PORT=6543
   DB_NAME=postgres
   ```

   Note: For local development without Supabase, you can skip creating the `.env` file. The application will automatically fall back to SQLite.

6. Apply database migrations:
   ```bash
   python manage.py migrate
   ```

7. Start the development server:
   ```bash
   python manage.py runserver
   ```

8. Visit http://127.0.0.1:8000/ in your browser to see the application.

## Project Structure

```
trimly/
├── main/                   # Main application
│   ├── models.py          # Database models
│   ├── views.py           # View functions
│   ├── templates/         # HTML templates
│   └── static/            # Static files (CSS, JS, images)
├── trimly/                # Project configuration
│   ├── settings.py        # Django settings
│   └── urls.py            # URL routing
└── manage.py              # Django management script
```

## Database Configuration

The project supports both PostgreSQL (Supabase) and SQLite:

- **PostgreSQL/Supabase**: Used in production and when all database environment variables are set in `.env`
- **SQLite**: Automatically used as fallback for local development when PostgreSQL credentials are not configured

## Contributing

1. Create a new branch for your feature:
   ```bash
   git checkout -b feature-name
   ```

2. Make your changes and commit them:
   ```bash
   git add .
   git commit -m "Description of changes"
   ```

3. Push to your branch:
   ```bash
   git push origin feature-name
   ```

4. Create a Pull Request on GitHub

## Troubleshooting

- If you see database connection errors, check that your `.env` file exists and has the correct credentials
- For local development, you can remove the `.env` file to use SQLite instead
- Make sure all dependencies are installed with `pip install -r requirements.txt`
- Ensure you're in the correct directory (trimly/) when running Django commands
# CSIT327-G7-Trimly
# CSIT327-G7-Trimly
