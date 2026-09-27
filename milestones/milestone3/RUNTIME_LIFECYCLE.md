# Part 4: Runtime lifecycle

Campus Seekr currently uses Python 3.14.7 in python:3.14.7-slim-trixie and PostgreSQL 16.6 in postgres:16.6-alpine3.20.

The shared-server and separate-worker options in Part 3 use the same application image. The function alternative would target the pricing reference platform's Python 3.14 runtime

## Support dates

- Python 3.14 in our containers: Support deadline: support expected through October 2030. Regular bug fixes until about October 2027.
- Reference function runtime: Python 3.14, Amazon Linux 2023: Support deadline: Deprecation June 30, 2029, new functions blocked July 31, updates blocked August 31.
- PostgreSQL 16: Support deadline: November 9, 2028.
- Debian 13: Support deadline: Full support through August 9, 2028
- Alpine 3.20: Support deadline: Normal support ended April 1, 2026, support is now listed as on request.

## Upgrade plan

- Devon: Review Python and its base image, track the managed runtime if we choose functions before Module 6 starts
- Doug: Update the PostgreSQL image and test backup/restore with existing data before Module 6 starts
- Parker:Review compatibility results and confirm the recorded versions before each upgrade is merged.