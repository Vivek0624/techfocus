# infra/aws — optional, nothing here deploys itself

| file | phase | what it is |
| --- | --- | --- |
| `iam-local-bedrock-policy.json` | B (local Bedrock) | least-privilege policy for the IAM user/role your AWS CLI profile uses |
| `iam-agentcore-invoke-policy.json` | C (AgentCore) | lets the local app invoke only your deployed runtime |
| `cloudformation/media-bucket.yaml` | API publishing | public-read `reels/` prefix so Meta can fetch videos; 7-day expiry |
| `cloudformation/scheduled-weekly-review.yaml` | cloud scheduling | EventBridge Scheduler → Lambda → AgentCore, weekly |

Validate without deploying:

    aws cloudformation validate-template --template-body file://cloudformation/media-bucket.yaml

Teardown (anything you deployed):

    aws cloudformation delete-stack --stack-name <stack>
    aws s3 rm s3://<bucket> --recursive   # before deleting the bucket stack
    agentcore remove ... && agentcore deploy   # or delete the runtime in the AgentCore console

Step Functions is intentionally not used yet: no current workflow needs multi-step durable retries in the cloud.
See docs/aws-setup.md for the full decision table.
