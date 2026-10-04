
## Amazon Web Services (AWS)

| Clause | Verdict | Evidence | URL |
|---|---|---|---|
| C1 runs OCI image, HTTPS URL | Requirements met by almost any AWS EC2 instance | Docs say that EC2 is flexible and can be told to run just about anything, including a container. | https://aws.amazon.com/ec2/ |
| C2 S3-compatible, SigV4 | Requirements fully met by standard AWS S3 storage | Amazon actually created Sigv4 for AWS, they still support it | https://docs.aws.amazon.com/mediatailor/latest/ug/channel-assembly-access-configuration-sigv4.html |
| C3 scoped credentials | Met fully by requesting temporary tokens | You can set up token management in any way you like, and scope them | https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc.html |
| C4 list + delete from a script | Possibly met, nothing I can find in the docs talks about if this is possible or not. | Although there are not specific directions, I am sure it is possible to set something up yourself. | No evidence one way or the other |
| C5 spend alert / hard cap | Met fully | You can set specific spend limits and notifications. | https://docs.aws.amazon.com/accounts/latest/reference/create-spend-limit.html |
| C6 free allowance or < $5 | Met with 5 GB free tier | AWS has good free tiers, and you start with 5GB free allowance. | https://aws.plainenglish.io/aws-free-tier-explained-whats-free-what-s-not-and-how-i-avoided-surprise-bills-17b9ca40c9b1 |