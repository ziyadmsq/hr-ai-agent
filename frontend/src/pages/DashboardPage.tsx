import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, FileText, MessageSquare, Bell } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";

interface DashboardStats {
  employeeCount: number;
  policyCount: number;
}

export default function DashboardPage() {
  const { user, org } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats>({
    employeeCount: 0,
    policyCount: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const [empRes, polRes] = await Promise.all([
          api.get("/v1/employees", { params: { page: 1, page_size: 1 } }),
          api.get("/v1/policies"),
        ]);
        setStats({
          employeeCount: empRes.data.total ?? 0,
          policyCount: polRes.data.total ?? 0,
        });
      } catch {
        // Stats are best-effort; silently ignore errors
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  const cards = [
    {
      title: "Employees",
      value: stats.employeeCount,
      icon: Users,
      path: "/employees",
      description: "Total employees",
    },
    {
      title: "Policies",
      value: stats.policyCount,
      icon: FileText,
      path: "/policies",
      description: "Active policies",
    },
    {
      title: "Chat",
      value: "AI Assistant",
      icon: MessageSquare,
      path: "/chat",
      description: "Ask HR questions",
    },
    {
      title: "Alerts",
      value: "View",
      icon: Bell,
      path: "/alerts",
      description: "Compliance alerts",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">
          Welcome back, {user?.full_name ?? "User"}
        </h2>
        <p className="text-muted-foreground">
          {org?.name ?? "Your Organization"} — HR Platform Dashboard
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Card
            key={card.title}
            className="cursor-pointer transition-shadow hover:shadow-md"
            onClick={() => navigate(card.path)}
          >
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                {card.title}
              </CardTitle>
              <card.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {loading ? "…" : card.value}
              </div>
              <p className="text-xs text-muted-foreground">
                {card.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => navigate("/chat")}>
            <MessageSquare className="mr-2 h-4 w-4" />
            Ask HR Assistant
          </Button>
          <Button variant="outline" onClick={() => navigate("/employees")}>
            <Users className="mr-2 h-4 w-4" />
            View Employees
          </Button>
          <Button variant="outline" onClick={() => navigate("/policies")}>
            <FileText className="mr-2 h-4 w-4" />
            Browse Policies
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

