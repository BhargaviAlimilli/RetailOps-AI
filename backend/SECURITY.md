# Local authentication and database limits

Login admits at most 10 attempts per normalized account and 30 per connected peer
per minute. The limiter retains at most 10,000 buckets and rejects new buckets at
capacity until inactive entries expire. Account keys are hashed. At most four
password checks execute concurrently; excess requests receive 429. These limits
are per process and reset on restart. Production multi-worker deployments require
a shared edge or datastore limiter and an explicit trusted-proxy configuration.

The database timeout setting bounds connection pool checkout and PostgreSQL
statement execution. Connection establishment also has a driver deadline. Database
operational failures and timeouts return a generic 503; logs contain the exception
class only. Integrity errors remain available to transaction services to resolve
business conflicts. Statement deadlines apply per statement, not per HTTP request.
