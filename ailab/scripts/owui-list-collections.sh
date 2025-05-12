#!/bin/bash
curl -X GET https://ami.inspection.alpha.canada.ca/api/v1/knowledge/list \
-H "Authorization: Bearer $TOKEN"
