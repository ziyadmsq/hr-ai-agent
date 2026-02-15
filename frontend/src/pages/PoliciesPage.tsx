import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import api from "@/lib/api";

interface Policy {
  id: string;
  title: string;
  content: string;
  category: string | null;
  is_active: boolean;
  updated_at: string;
}

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Policy | null>(null);

  useEffect(() => {
    async function fetchPolicies() {
      try {
        const { data } = await api.get("/v1/policies");
        setPolicies(data.items);
      } catch {
        // silently handle
      } finally {
        setLoading(false);
      }
    }
    fetchPolicies();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Badge variant="secondary">{policies.length} policies</Badge>
      </div>

      {loading ? (
        <p className="text-muted-foreground py-8 text-center">Loading…</p>
      ) : policies.length === 0 ? (
        <p className="text-muted-foreground py-8 text-center">
          No policies found. Policies can be added by an admin.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {policies.map((policy) => (
            <Card
              key={policy.id}
              className="cursor-pointer transition-shadow hover:shadow-md"
              onClick={() => setSelected(policy)}
            >
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{policy.title}</CardTitle>
                  {policy.category && (
                    <Badge variant="outline">{policy.category}</Badge>
                  )}
                </div>
                <CardDescription>
                  Updated{" "}
                  {new Date(policy.updated_at).toLocaleDateString()}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {policy.content}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!selected} onOpenChange={() => setSelected(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>{selected?.title}</DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh]">
            <div className="whitespace-pre-wrap text-sm pr-4">
              {selected?.content}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}

