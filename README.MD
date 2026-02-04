=== Nastavenie virtuálneho prostredia ===
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

=== Nastavenie databázy ===
Je potrebné mať nainštalovanú postgreSQL databázu
V repozitári je uložený dump databázy s názvom pharmacogenic.sql 
Na restornutie databázy stačí zadať tieto príkazy do databázy
createdb pharmacogenomic_data && psql pharmacogenomic_data < pharmacogenomic_data.sql

Na konfiguráciu databázy s aplikáciou je potrebné zmeniť prikaz psycopg2.connect() vo funkciách get_connection() a ensure_db_running()
typu:
 psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres", 
        password="heslo123",
        database="pharmacogenomic_data"
    )
na základe údajov vašich z databázy.

=== Upravenie spracovávania ===
Kód bol upravený na batch systém a limity sa nastavujú v server.py (line 481) 
momentálne nastavenie:
            MAX_ANNOTATED = -1
            MAX_TOTAL = -1
nemá žiadne limitácie. 
line 486:
 for batch_variants, batch_errors in parse_vcf_file_stream(tmp_path, batch_size=50000):
tu sa nastavuje batch_size na základe veľkosti RAMKY- t.j. pri väčší RAMkách je kľude možné nastaviť väčší batch.

=== Spustenie aplikácie ===
Aplikácia sa zapína príkazom:
shiny run app/app.py

