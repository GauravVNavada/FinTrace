import assert from "node:assert/strict";
import test from "node:test";
// @ts-expect-error Node's strip-types test runner requires the explicit .ts extension.
import { loadExceptionDetail } from "./exception-detail-loader.ts";

test("forbidden audit access does not block exception and lifecycle loading", async () => {
  const result = await loadExceptionDetail("EXC-1042", {
    fetchException: async exceptionId => ({ id: exceptionId, order_id: "ORD-2041" }),
    fetchLifecycle: async orderId => ({ orderId, payments: [{ payment_id: "PAY-1" }] }),
    fetchAuditEvents: async () => { throw { status: 403 }; },
    isForbiddenError: error => typeof error === "object" && error !== null && "status" in error && error.status === 403,
  });

  assert.equal(result.exception.id, "EXC-1042");
  assert.equal(result.lifecycle.orderId, "ORD-2041");
  assert.deepEqual(result.auditEvents, []);
  assert.equal(result.auditAccess, "forbidden");
});
