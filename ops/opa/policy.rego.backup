package authz

default allow = false

audit_log := {
  "decision_id": input.decision_id,
  "user": input.user,
  "action": input.action,
  "resource": input.resource,
  "allowed": allow
}

allow {
  is_super_admin
}

allow {
  not is_super_admin
  input.action == "health:read"
}

is_super_admin {
  user_roles := input.user.roles
  user_roles != null
  "super_admin" in user_roles
}
