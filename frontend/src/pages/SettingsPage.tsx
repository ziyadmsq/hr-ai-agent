import { useEffect, useState, type FormEvent } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";

interface OrgData {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export default function SettingsPage() {
  const { user, org, setOrg } = useAuth();
  const { toast } = useToast();
  const [orgData, setOrgData] = useState<OrgData | null>(null);
  const [orgName, setOrgName] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchOrg() {
      try {
        const { data } = await api.get("/v1/org");
        setOrgData(data);
        setOrgName(data.name);
      } catch {
        // silently handle
      } finally {
        setLoading(false);
      }
    }
    fetchOrg();
  }, []);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!orgName.trim()) return;
    setSaving(true);
    try {
      const { data } = await api.patch("/v1/org", { name: orgName.trim() });
      setOrgData(data);
      setOrg({ id: data.id, name: data.name, slug: data.slug });
      toast({ title: "Saved", description: "Organization name updated." });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to update settings.";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  const isAdmin = user?.role === "admin";

  return (
    <div className="space-y-6 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Organization</CardTitle>
          <CardDescription>
            Manage your organization settings.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <form onSubmit={handleSave} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="orgName" className="text-sm font-medium">
                  Organization Name
                </label>
                <Input
                  id="orgName"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  disabled={!isAdmin}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Slug</label>
                <p className="text-sm text-muted-foreground">
                  {orgData?.slug}
                </p>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Created</label>
                <p className="text-sm text-muted-foreground">
                  {orgData?.created_at
                    ? new Date(orgData.created_at).toLocaleDateString()
                    : "—"}
                </p>
              </div>
              {isAdmin && (
                <Button type="submit" disabled={saving}>
                  {saving ? "Saving…" : "Save Changes"}
                </Button>
              )}
              {!isAdmin && (
                <p className="text-xs text-muted-foreground">
                  Only admins can edit organization settings.
                </p>
              )}
            </form>
          )}
        </CardContent>
      </Card>

      <Separator />

      <Card>
        <CardHeader>
          <CardTitle>Your Profile</CardTitle>
          <CardDescription>Your account information.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Name</span>
            <span className="text-sm text-muted-foreground">
              {user?.full_name}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Email</span>
            <span className="text-sm text-muted-foreground">
              {user?.email}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Role</span>
            <Badge variant="secondary">{user?.role}</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Organization</span>
            <span className="text-sm text-muted-foreground">
              {org?.name}
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

