-- Loads the seed CSVs. Paths are relative to the db/ directory; run via
-- db/setup.sh or `flask db-init`, which cd into that directory first.
\COPY Users FROM 'data/Users.csv' WITH DELIMITER ',' NULL '' CSV HEADER
SELECT pg_catalog.setval('users_id_seq', (SELECT MAX(id) FROM Users), true);

\COPY Sports FROM 'data/Sports.csv' WITH DELIMITER ',' NULL '' CSV HEADER
SELECT pg_catalog.setval('sports_id_seq', (SELECT MAX(id) FROM Sports), true);

\COPY Games FROM 'data/Games.csv' WITH DELIMITER ',' NULL '' CSV HEADER
SELECT pg_catalog.setval('games_id_seq', (SELECT MAX(id) FROM Games), true);

\COPY Books FROM 'data/Books.csv' WITH DELIMITER ',' NULL '' CSV HEADER
SELECT pg_catalog.setval('books_id_seq', (SELECT MAX(id) FROM Books), true);

\COPY Lines FROM 'data/Lines.csv' WITH DELIMITER ',' NULL '' CSV HEADER
SELECT pg_catalog.setval('lines_id_seq', (SELECT MAX(id) FROM Lines), true);

\COPY BetSlips FROM 'data/BetSlips.csv' WITH DELIMITER ',' NULL '' CSV HEADER
SELECT pg_catalog.setval('betslips_id_seq', (SELECT MAX(id) FROM BetSlips), true);

\COPY SlipLegs FROM 'data/SlipLegs.csv' WITH DELIMITER ',' NULL '' CSV HEADER
SELECT pg_catalog.setval('sliplegs_id_seq', (SELECT MAX(id) FROM SlipLegs), true);

\COPY BalanceTransactions FROM 'data/BalanceTransactions.csv' WITH DELIMITER ',' NULL '' CSV HEADER
SELECT pg_catalog.setval('balancetransactions_id_seq', (SELECT MAX(id) FROM BalanceTransactions), true);

\COPY CartItems FROM 'data/CartItems.csv' WITH DELIMITER ',' NULL '' CSV HEADER
