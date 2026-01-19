-- 1. Удаляем таблицу, если она уже существует (на случай повторного запуска)
-- DROP TABLE IF EXISTS public.users CASCADE;


select * from users;


-- 2. Создаём таблицу с нужным порядком столбцов
CREATE TABLE public.users (
    id              BIGSERIAL PRIMARY KEY,
    
    telegram_id     BIGINT          NOT NULL UNIQUE,              -- главный идентификатор пользователя
	username        TEXT            NOT NULL,

	created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
	
    full_name       TEXT            NOT NULL CHECK (            
        TRIM(full_name) <> '' 
        AND LENGTH(TRIM(full_name)) >= 5
    ),
   
    
    group_number    CHAR(6)         NOT NULL CHECK (group_number ~ '^[0-9]{6}$'),
    faculty         TEXT            NOT NULL,
    
    mobile_number   VARCHAR(20)     NOT NULL CHECK (mobile_number ~ '^\+?[0-9\s-]{9,18}$'),
    stud_number     VARCHAR(20)     NOT NULL CHECK (stud_number ~ '^[0-9]{7,12}$'),
    
    form_educ       VARCHAR(30)     NOT NULL,
    scholarship     BOOLEAN         NOT NULL DEFAULT FALSE,
    
    is_verified     BOOLEAN         NOT NULL DEFAULT FALSE,
    verified_at     TIMESTAMPTZ
);

-- 3. Полезные индексы
CREATE INDEX idx_users_telegram_id     ON public.users (telegram_id);
CREATE INDEX idx_users_is_verified     ON public.users (is_verified);
CREATE INDEX idx_users_group_number    ON public.users (group_number);

-- 4. Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. Триггер на обновление updated_at
DROP TRIGGER IF EXISTS trigger_update_timestamp ON public.users;
CREATE TRIGGER trigger_update_timestamp
    BEFORE UPDATE ON public.users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();



-- 1. Делаем необязательными все поля, которые заполняются позже
ALTER TABLE users
    ALTER COLUMN full_name     DROP NOT NULL,
    ALTER COLUMN group_number  DROP NOT NULL,
    ALTER COLUMN faculty       DROP NOT NULL,
    ALTER COLUMN mobile_number DROP NOT NULL,
    ALTER COLUMN stud_number   DROP NOT NULL,
    ALTER COLUMN form_educ     DROP NOT NULL;

-- 2. Для scholarship можно оставить NOT NULL с дефолтом false (или тоже сделать NULLable)
-- Если хотите разрешить отсутствие информации о стипендии:
-- ALTER TABLE users ALTER COLUMN scholarship DROP NOT NULL;

-- 3. Убираем ограничения CHECK для полей, которые могут быть NULL
-- (иначе PostgreSQL не позволит вставить NULL в поле с CHECK)
ALTER TABLE users DROP CONSTRAINT users_full_name_check;
ALTER TABLE users DROP CONSTRAINT users_group_number_check;
ALTER TABLE users DROP CONSTRAINT users_mobile_number_check;
ALTER TABLE users DROP CONSTRAINT users_stud_number_check;

-- 4. (Опционально) Можно вернуть проверки, но уже с учётом NULL
-- Пример для group_number:
ALTER TABLE users
    ADD CONSTRAINT users_group_number_check
    CHECK (group_number IS NULL OR group_number ~ '^[0-9]{6}$');

-- Аналогично можно сделать для других полей, если нужно

CREATE OR REPLACE FUNCTION try_verify_user(p_telegram_id bigint)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    v_count int;
BEGIN
    -- Проверяем, что все ключевые поля заполнены
    SELECT COUNT(*)
    INTO v_count
    FROM users
    WHERE telegram_id = p_telegram_id
      AND full_name     IS NOT NULL
      AND group_number  IS NOT NULL
      AND faculty       IS NOT NULL
      AND mobile_number IS NOT NULL
      AND stud_number   IS NOT NULL
      AND form_educ     IS NOT NULL
      AND is_verified   = false;

    IF v_count = 1 THEN
        UPDATE users
           SET is_verified = true,
               verified_at = now()
         WHERE telegram_id = p_telegram_id;
         
        RETURN true;   -- успешно верифицировали
    END IF;

    RETURN false;      -- ещё не все поля заполнены
END;
$$;



-- Убираем старые CHECK, которые не позволяют NULL
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_full_name_check;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_group_number_check;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_mobile_number_check;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_stud_number_check;

-- Добавляем новые проверки, которые разрешают NULL
ALTER TABLE users
    ADD CONSTRAINT users_full_name_check
    CHECK (full_name IS NULL OR TRIM(full_name) <> '' AND length(TRIM(full_name)) >= 5);

ALTER TABLE users
    ADD CONSTRAINT users_group_number_check
    CHECK (group_number IS NULL OR group_number ~ '^[0-9]{6}$');

ALTER TABLE users
    ADD CONSTRAINT users_mobile_number_check
    CHECK (mobile_number IS NULL OR mobile_number ~ '^\+?[0-9\s-]{9,18}$');

ALTER TABLE users
    ADD CONSTRAINT users_stud_number_check
    CHECK (stud_number IS NULL OR stud_number ~ '^[0-9]{7,12}$');

-- Если нужно — можно добавить и для faculty и form_educ
ALTER TABLE users
    ADD CONSTRAINT users_faculty_check
    CHECK (faculty IS NULL OR length(TRIM(faculty)) >= 1);

ALTER TABLE users
    ADD CONSTRAINT users_form_educ_check
    CHECK (form_educ IS NULL OR form_educ IN ('бюджет', 'платное'));




CREATE OR REPLACE FUNCTION try_verify_user(p_telegram_id bigint)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    v_count int;
BEGIN
    SELECT COUNT(*)
    INTO v_count
    FROM users
    WHERE telegram_id = p_telegram_id
      AND full_name     IS NOT NULL
      AND group_number  IS NOT NULL
      AND faculty       IS NOT NULL
      AND mobile_number IS NOT NULL
      AND stud_number   IS NOT NULL
      AND form_educ     IS NOT NULL
      AND is_verified   = false;

    IF v_count = 1 THEN
        UPDATE users
           SET is_verified = true,
               verified_at = now(),
               updated_at  = now()
         WHERE telegram_id = p_telegram_id;

        RETURN true;
    END IF;

    RETURN false;
END;
$$;




	