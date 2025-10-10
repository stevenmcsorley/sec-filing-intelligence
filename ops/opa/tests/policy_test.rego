package authz

# Test super_admin role
test_super_admin_allows_all {
    allow with input as {
        "decision_id": "test-1",
        "user": {
            "id": "admin-123",
            "roles": ["super_admin"],
        },
        "action": "any:action",
        "resource": {}
    }
}

test_super_admin_allows_even_restricted_actions {
    allow with input as {
        "decision_id": "test-2",
        "user": {
            "id": "admin-123",
            "roles": ["super_admin", "analyst_pro"],
        },
        "action": "admin:delete_all",
        "resource": {}
    }
}

# Test health:read action (should be allowed for all)
test_health_read_allowed_for_basic_user {
    allow with input as {
        "decision_id": "test-3",
        "user": {
            "id": "user-456",
            "roles": ["basic_free"],
        },
        "action": "health:read",
        "resource": {}
    }
}

test_health_read_allowed_for_analyst {
    allow with input as {
        "decision_id": "test-4",
        "user": {
            "id": "user-789",
            "roles": ["analyst_pro"],
        },
        "action": "health:read",
        "resource": {}
    }
}

# Test default deny behavior
test_unauthorized_action_denied {
    not allow with input as {
        "decision_id": "test-5",
        "user": {
            "id": "user-111",
            "roles": ["basic_free"],
        },
        "action": "admin:delete",
        "resource": {}
    }
}

test_unknown_action_denied_for_basic {
    not allow with input as {
        "decision_id": "test-6",
        "user": {
            "id": "user-222",
            "roles": ["basic_free"],
        },
        "action": "unknown:action",
        "resource": {}
    }
}

# Test audit log generation
test_audit_log_contains_decision_details {
    audit_log.decision_id == "test-7" with input as {
        "decision_id": "test-7",
        "user": {
            "id": "user-333",
            "roles": ["analyst_pro"],
        },
        "action": "alerts:view",
        "resource": {
            "org_id": "org-123"
        }
    }
}

test_audit_log_captures_user_context {
    audit_log.user.id == "user-444" with input as {
        "decision_id": "test-8",
        "user": {
            "id": "user-444",
            "roles": ["basic_free"],
        },
        "action": "filings:read",
        "resource": {}
    }
}

test_audit_log_records_allow_decision {
    audit_log.allowed == true with input as {
        "decision_id": "test-9",
        "user": {
            "id": "admin-999",
            "roles": ["super_admin"],
        },
        "action": "any:action",
        "resource": {}
    }
}

test_audit_log_records_deny_decision {
    audit_log.allowed == false with input as {
        "decision_id": "test-10",
        "user": {
            "id": "user-555",
            "roles": ["basic_free"],
        },
        "action": "admin:delete",
        "resource": {}
    }
}

# Test is_super_admin helper
test_is_super_admin_true_for_super_admin_role {
    is_super_admin with input as {
        "decision_id": "test-11",
        "user": {
            "id": "admin-888",
            "roles": ["super_admin"],
        },
        "action": "test",
        "resource": {}
    }
}

test_is_super_admin_false_for_non_admin {
    not is_super_admin with input as {
        "decision_id": "test-12",
        "user": {
            "id": "user-666",
            "roles": ["analyst_pro"],
        },
        "action": "test",
        "resource": {}
    }
}

test_is_super_admin_false_for_empty_roles {
    not is_super_admin with input as {
        "decision_id": "test-13",
        "user": {
            "id": "user-777",
            "roles": [],
        },
        "action": "test",
        "resource": {}
    }
}

test_is_super_admin_false_for_null_roles {
    not is_super_admin with input as {
        "decision_id": "test-14",
        "user": {
            "id": "user-888",
            "roles": null,
        },
        "action": "test",
        "resource": {}
    }
}
