-- Initialize PostgreSQL with required extensions

-- Enable uuid-ossp for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE rhasspy TO rhasspy;
