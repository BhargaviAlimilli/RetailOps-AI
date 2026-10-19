# Retail API conventions

- Prefix: `/api/v1`; development OpenAPI UI: `/docs`.
- Health is public. Retail operations require `Authorization: Bearer <opaque token>`. Login returns token and user; logout revokes the stored session. Browser credentials remain in memory.
- Admin and manager can modify business data. Analyst is read-only. Backend endpoints and mutation services enforce roles.
- UUID resource identifiers; money and percentages are JSON decimal strings. Currency is INR in the synthetic single-organization demonstration.
- UTC timestamps. Reporting start/end dates are inclusive calendar dates, translated into a half-open UTC interval. Maximum 366 days; supported years 1900 through 2100. Previous-period comparisons use the same duration; a zero previous revenue yields null percentage change.
- Paginated collections return `items`, `total`, `page`, `page_size`; page size defaults to 20 and caps at 100. Literal search escapes wildcard characters.
- Validation 422 responses omit original input/context. Authentication 401, authorization 403, missing 404, state/duplicate conflicts 409 and unavailable database 503 are explicit failures. Request IDs are returned in `X-Request-ID`.
- Inventory uses on-hand minus reserved as available. Zero available is out of stock; positive available at/below reorder point is low stock. Inventory valuation uses current product cost; sales profit uses historical sale-item cost.
- The first release is one retail organization. All authenticated roles may read all its stores, sales and supplier costs. Future multi-organization isolation requires a distinct reviewed security boundary.
