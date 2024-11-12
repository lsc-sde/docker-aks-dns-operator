---
title: Container Image
parent: AKS DNS Operator
layout: page
grand_parent: Environment Specific Components
---

This operator will look for the annotation **xlscsde.nhs.uk/dns-record** on any service or ingress resources in the system, it will then add an entry for this record in to a predefined private dns zone alongside any prefix that is included.

If any changes are made to the IP addresses that are published by the service or ingress, the service or ingress will be updated which in turn will trigger the operator to update the record to reflect the change.