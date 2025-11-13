

# TRIMLY


**Trimly** is a haircut reservation system built with Django and Supabase, enabling users to book appointments, manage schedules, and efficiently handle customer data. This project is a collaboration between IT317 – Project Management G1 and CSIT327 – Information Management 2 G7.

## Tech Stack

| Category | Technology |
|-----------|-------------|
| **Backend** | Django 5.2.7+ |
| **Frontend** | HTML, CSS |
| **Database (Local)** | SQLite |
| **Database (Production)** | PostgreSQL (via Supabase) |
| **Environment Management** | python-dotenv |
| **Database Adapter** | psycopg2-binary |
| **Supabase Client** | supabase-py |


## Setup & run instructions

Get up and running in 3 simple steps:

```bash
# 1. Clone the repo
git clone https://github.com/jace54321/CSIT327-G7-Trimly.git
cd csit327-g7-trimly/trimly

# 2. Set up environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# 3. Run migrations and start server
python manage.py migrate
python manage.py runserver
```

Open your browser: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

> Optional: Create a `.env` file for Supabase/PostgreSQL credentials. Without it, SQLite will be used automatically.

## Project Structure

```
trimly/
├── main/           # App: models, views, templates, static files
├── trimly/         # Project config: settings.py, urls.py
└── manage.py       # Django management
```

## Team Members

### Developers

| Name                 | Role                 | CIT-U Email                                                       |
| -------------------- | -------------------- | ----------------------------------------------------------------- |
| Lord Anthone Acebedo | Lead Developer       | [lordanthone.acebedo@cit.edu](mailto:lordanthone.acebedo@cit.edu) |
| Kenneth Alicaba      | Developer (Frontend) | [kenneth.alicaba@cit.edu](mailto:kenneth.alicaba@cit.edu)         |
| Joseph Cris Arpon    | Developer (Backend)  | [josephcris.arpon@cit.edu](mailto:josephcris.arpon@cit.edu)       |

### Project Managers & Analysts

| Name                     | Role             | CIT-U Email                                                               |
| ------------------------ | ---------------- | ------------------------------------------------------------------------- |
| Ace Denver Abella        | Product Owner    | [acedenver.abella@cit.edu](mailto:acedenver.abella@cit.edu)               |
| Treasure Louise Abadinas | Business Analyst | [treasurelouise.abadinas@cit.edu](mailto:treasurelouise.abadinas@cit.edu) |
| Myron Deandre Alia       | Business Analyst | [myrondeandre.alia@cit.edu](mailto:myrondeandre.alia@cit.edu)             |
| Zydric Abel              | Scrum Master     | [zydric.abel@cit.edu](mailto:zydric.abel@cit.edu)                         |

## Deployed Link
    https://trimly-euq5.onrender.com/

*(404)*

## Troubleshooting

* Verify `.env` credentials for Supabase/PostgreSQL or remove the file for SQLite fallback.
* Make sure dependencies are installed with `pip install -r requirements.txt`.
* Run Django commands inside the `trimly/` directory.

---


