import { useEffect, useState, useCallback } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import api from "@/lib/api";

interface Employee {
  id: string;
  full_name: string;
  email: string;
  employee_code: string;
  department: string | null;
  position: string | null;
  status: string;
  hire_date: string | null;
}

interface EmployeeDetail {
  id: string;
  organization_id: string;
  employee_code: string;
  full_name: string;
  email: string;
  department: string | null;
  position: string | null;
  hire_date: string | null;
  status: string;
  metadata_: Record<string, unknown> | null;
  created_at: string;
}

interface LeaveBalance {
  id: string;
  employee_id: string;
  leave_type: string;
  total_days: number;
  used_days: number;
  remaining_days: number;
  year: number;
}

interface LeaveRequest {
  id: string;
  employee_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  status: string;
  reason: string | null;
  approved_by: string | null;
  created_at: string;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function leaveStatusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  switch (status.toLowerCase()) {
    case "approved":
      return "default";
    case "rejected":
      return "destructive";
    case "pending":
    default:
      return "outline";
  }
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [department, setDepartment] = useState("");
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  // Sheet state
  const [sheetOpen, setSheetOpen] = useState(false);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const [employeeDetail, setEmployeeDetail] = useState<EmployeeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Leave balances state
  const [leaveBalances, setLeaveBalances] = useState<LeaveBalance[]>([]);
  const [balancesLoading, setBalancesLoading] = useState(false);
  const [balancesError, setBalancesError] = useState<string | null>(null);

  // Leave requests state
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequest[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [requestsError, setRequestsError] = useState<string | null>(null);

  const fetchEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
      };
      if (department.trim()) params.department = department.trim();
      const { data } = await api.get("/v1/employees", { params });
      setEmployees(data.items);
      setTotal(data.total);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [page, department]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  const handleRowClick = (employeeId: string) => {
    setSelectedEmployeeId(employeeId);
    setSheetOpen(true);
    setEmployeeDetail(null);
    setDetailError(null);
    setLeaveBalances([]);
    setBalancesError(null);
    setLeaveRequests([]);
    setRequestsError(null);
    fetchEmployeeDetail(employeeId);
  };

  const fetchEmployeeDetail = async (employeeId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const { data } = await api.get(`/v1/employees/${employeeId}`);
      setEmployeeDetail(data);
    } catch {
      setDetailError("Failed to load employee details.");
    } finally {
      setDetailLoading(false);
    }
  };

  const fetchLeaveBalances = async (employeeId: string) => {
    setBalancesLoading(true);
    setBalancesError(null);
    try {
      const { data } = await api.get("/v1/leave/balance", {
        params: { employee_id: employeeId },
      });
      setLeaveBalances(Array.isArray(data) ? data : []);
    } catch {
      setBalancesError("Failed to load leave balances.");
    } finally {
      setBalancesLoading(false);
    }
  };

  const fetchLeaveRequests = async (employeeId: string) => {
    setRequestsLoading(true);
    setRequestsError(null);
    try {
      const { data } = await api.get("/v1/leave/requests", {
        params: { employee_id: employeeId },
      });
      setLeaveRequests(data.items ?? []);
    } catch {
      setRequestsError("Failed to load leave requests.");
    } finally {
      setRequestsLoading(false);
    }
  };

  const handleTabChange = (value: string) => {
    if (!selectedEmployeeId) return;
    if (value === "balances" && leaveBalances.length === 0 && !balancesLoading && !balancesError) {
      fetchLeaveBalances(selectedEmployeeId);
    }
    if (value === "requests" && leaveRequests.length === 0 && !requestsLoading && !requestsError) {
      fetchLeaveRequests(selectedEmployeeId);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Filter by department…"
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value);
              setPage(1);
            }}
            className="pl-8"
          />
        </div>
        <Badge variant="secondary">{total} employees</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Employee Directory</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground py-8 text-center">Loading…</p>
          ) : employees.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center">
              No employees found.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-medium">Name</th>
                    <th className="pb-2 font-medium">Email</th>
                    <th className="pb-2 font-medium">Code</th>
                    <th className="pb-2 font-medium">Department</th>
                    <th className="pb-2 font-medium">Position</th>
                    <th className="pb-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((emp) => (
                    <tr
                      key={emp.id}
                      className="border-b last:border-0 cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => handleRowClick(emp.id)}
                    >
                      <td className="py-2 font-medium">{emp.full_name}</td>
                      <td className="py-2 text-muted-foreground">
                        {emp.email}
                      </td>
                      <td className="py-2">{emp.employee_code}</td>
                      <td className="py-2">{emp.department ?? "—"}</td>
                      <td className="py-2">{emp.position ?? "—"}</td>
                      <td className="py-2">
                        <Badge
                          variant={
                            emp.status === "active" ? "default" : "secondary"
                          }
                        >
                          {emp.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Employee Detail Sheet */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="sm:max-w-[480px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>
              {detailLoading ? (
                <Skeleton className="h-6 w-48" />
              ) : (
                employeeDetail?.full_name ?? "Employee Details"
              )}
            </SheetTitle>
            <SheetDescription>
              {detailLoading ? (
                <Skeleton className="h-4 w-36" />
              ) : employeeDetail ? (
                <span className="flex items-center gap-2">
                  {employeeDetail.employee_code}
                  <Badge
                    variant={
                      employeeDetail.status === "active" ? "default" : "secondary"
                    }
                  >
                    {employeeDetail.status}
                  </Badge>
                </span>
              ) : null}
            </SheetDescription>
          </SheetHeader>

          {detailError && (
            <p className="text-sm text-destructive mt-4">{detailError}</p>
          )}

          <Separator className="my-4" />

          <Tabs defaultValue="profile" onValueChange={handleTabChange}>
            <TabsList className="w-full">
              <TabsTrigger value="profile" className="flex-1">Profile</TabsTrigger>
              <TabsTrigger value="balances" className="flex-1">Leave Balances</TabsTrigger>
              <TabsTrigger value="requests" className="flex-1">Leave Requests</TabsTrigger>
            </TabsList>

            {/* Profile Tab */}
            <TabsContent value="profile">
              {detailLoading ? (
                <div className="space-y-4 mt-4">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="space-y-1">
                      <Skeleton className="h-3 w-24" />
                      <Skeleton className="h-5 w-48" />
                    </div>
                  ))}
                </div>
              ) : employeeDetail ? (
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Full Name</p>
                    <p className="text-sm font-medium">{employeeDetail.full_name}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Email</p>
                    <p className="text-sm font-medium">{employeeDetail.email}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Employee Code</p>
                    <p className="text-sm font-medium">{employeeDetail.employee_code}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Department</p>
                    <p className="text-sm font-medium">{employeeDetail.department ?? "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Position</p>
                    <p className="text-sm font-medium">{employeeDetail.position ?? "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Hire Date</p>
                    <p className="text-sm font-medium">{formatDate(employeeDetail.hire_date)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Status</p>
                    <p className="text-sm font-medium capitalize">{employeeDetail.status}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Created At</p>
                    <p className="text-sm font-medium">{formatDate(employeeDetail.created_at)}</p>
                  </div>
                </div>
              ) : null}
            </TabsContent>

            {/* Leave Balances Tab */}
            <TabsContent value="balances">
              {balancesLoading ? (
                <div className="space-y-3 mt-4">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-24 w-full rounded-lg" />
                  ))}
                </div>
              ) : balancesError ? (
                <p className="text-sm text-destructive mt-4">{balancesError}</p>
              ) : leaveBalances.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  No leave balances found.
                </p>
              ) : (
                <div className="space-y-3 mt-4">
                  {leaveBalances.map((balance) => (
                    <div
                      key={balance.id}
                      className="rounded-lg border p-4 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium capitalize">
                          {balance.leave_type}
                        </p>
                        <Badge variant="secondary">{balance.year}</Badge>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div>
                          <p className="text-xs text-muted-foreground">Total</p>
                          <p className="text-lg font-semibold">{balance.total_days}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Used</p>
                          <p className="text-lg font-semibold">{balance.used_days}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Remaining</p>
                          <p className="text-lg font-semibold">{balance.remaining_days}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            {/* Leave Requests Tab */}
            <TabsContent value="requests">
              {requestsLoading ? (
                <div className="space-y-3 mt-4">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full rounded-lg" />
                  ))}
                </div>
              ) : requestsError ? (
                <p className="text-sm text-destructive mt-4">{requestsError}</p>
              ) : leaveRequests.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  No leave requests found.
                </p>
              ) : (
                <div className="space-y-3 mt-4">
                  {leaveRequests.map((req) => (
                    <div
                      key={req.id}
                      className="rounded-lg border p-4 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium capitalize">
                          {req.leave_type}
                        </p>
                        <Badge
                          variant={leaveStatusVariant(req.status)}
                          className={
                            req.status.toLowerCase() === "approved"
                              ? "bg-green-600 text-white hover:bg-green-600/80"
                              : req.status.toLowerCase() === "pending"
                                ? "border-yellow-500 text-yellow-600"
                                : undefined
                          }
                        >
                          {req.status}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatDate(req.start_date)} — {formatDate(req.end_date)}
                      </div>
                      {req.reason && (
                        <p className="text-sm text-muted-foreground">{req.reason}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>
    </div>
  );
}
