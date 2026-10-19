## 5b
Our adapter_enumerate enumerates all services within our ECS cluster and region. We do not need to enumerate any regions other than our own (us-east-2), our services only exist within our region. We will need to update adapter_enumerate in order to empty and delete any and all S3 buckets that we use for our service.
## 5c

'lifecycle { prevent_destroy = true }' - Not present.

Deletion protection at the provider - AWS supports deletion protection in the form of object locking; it requires versioning to be enabled so it will not be a problem so long as we do not enable versioning. - https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html

A versioned bucket that still has content - We will need to ensure ```app/ports/storage.py:empty_bucket``` is ran in our adapter_enumerate when we update it to support our S3 buckets.

An automatic final snapshot - AWS supports EBS snapshots, however, it does not create them automatically by default, so unless we need the snapshots and create them ourselves in the future, we should not need to enumerate or destroy them in our script. - https://docs.aws.amazon.com/ebs/latest/userguide/ebs-creating-snapshot.html 