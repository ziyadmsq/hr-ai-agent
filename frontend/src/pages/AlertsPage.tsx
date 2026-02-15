import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Bell, ShieldCheck, TrendingDown } from "lucide-react";

const alertTypes = [
  {
    title: "Compliance Alerts",
    description:
      "Monitors policy compliance across the organization. Alerts trigger when employees miss required training or policy acknowledgments.",
    icon: ShieldCheck,
    status: "Active",
  },
  {
    title: "Sentiment Alerts",
    description:
      "Tracks employee sentiment from chat interactions. Alerts trigger when negative sentiment patterns are detected.",
    icon: TrendingDown,
    status: "Active",
  },
  {
    title: "Leave Alerts",
    description:
      "Monitors leave balance thresholds and unusual absence patterns across departments.",
    icon: Bell,
    status: "Active",
  },
];

export default function AlertsPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-muted-foreground">
          Configure and monitor automated HR alerts for your organization.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {alertTypes.map((alert) => (
          <Card key={alert.title}>
            <CardHeader>
              <div className="flex items-start justify-between">
                <alert.icon className="h-8 w-8 text-muted-foreground" />
                <Badge variant="secondary">{alert.status}</Badge>
              </div>
              <CardTitle className="text-base">{alert.title}</CardTitle>
              <CardDescription>{alert.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                No recent events
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Alert Events</CardTitle>
          <CardDescription>
            Alert events will appear here when triggered by the system.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="py-8 text-center text-muted-foreground">
            No alert events yet. Alerts will be triggered automatically based on
            configured rules.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

