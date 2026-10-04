## Lifecycle Proposal
Abort any incomplete, multipart uploads after 24 hours. Versioning should be enabled and non-current versions of items should be removed after two weeks have elapsed. Storage-class transitions will not be necessary.

## Egress Reasoning
Date: 10/4/2026
Egress pricing for both MS Azure and AWS varies based on region. Prices below assume East US as the region.

#### AWS
For AWS, the price of data retrieval requests (GET, SELECT) is $0.0004 per request. 

https://aws.amazon.com/s3/pricing/

#### MS Azure
For MS Azure, the egress pricing further depends on the Blob's tier (premium: $0.0014 per 10000 requests, hot: $0.004 per 10000 requests, cool: $0.01 per 10000 requests, cold: $0.10 per 10000 requests, archive: $5 per 10000 requests, $50 per 10000 requests if the retrieval is high prioirity).

https://azure.microsoft.com/en-us/pricing/details/storage/blobs/