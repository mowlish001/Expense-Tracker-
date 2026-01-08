create database expence_tracker;
use expence_tracker;
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255)
);

CREATE TABLE expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    title VARCHAR(100),
    category VARCHAR(100),
    amount DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

select * from users;
select * from expenses;
ALTER TABLE expenses ADD expense_date DATE;


ALTER TABLE users
ADD COLUMN monthly_income FLOAT DEFAULT 0,
ADD COLUMN profile_photo VARCHAR(255) NULL;

