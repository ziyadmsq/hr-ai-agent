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

interface AIConfig {
  provider: string | null;
  model: string | null;
  api_key: string | null;
  base_url: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
}

const DEFAULT_MODELS: Record<string, string> = {
  openai: "gpt-4o-mini",
  groq: "llama-3.3-70b-versatile",
  ollama: "llama3",
};

const DEFAULT_EMBEDDING_MODELS: Record<string, string> = {
  openai: "text-embedding-3-small",
  ollama: "nomic-embed-text",
};

export default function SettingsPage() {
  const { user, org, setOrg } = useAuth();
  const { toast } = useToast();
  const [orgData, setOrgData] = useState<OrgData | null>(null);
  const [orgName, setOrgName] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  // AI Config state
  const [aiConfig, setAiConfig] = useState<AIConfig>({
    provider: null,
    model: null,
    api_key: null,
    base_url: null,
    embedding_provider: null,
    embedding_model: null,
  });
  const [aiProvider, setAiProvider] = useState("openai");
  const [aiModel, setAiModel] = useState("");
  const [aiApiKey, setAiApiKey] = useState("");
  const [aiBaseUrl, setAiBaseUrl] = useState("");
  const [aiEmbeddingProvider, setAiEmbeddingProvider] = useState("openai");
  const [aiEmbeddingModel, setAiEmbeddingModel] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [savingAi, setSavingAi] = useState(false);
  const [loadingAi, setLoadingAi] = useState(true);
  const [originalApiKey, setOriginalApiKey] = useState("");

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

  useEffect(() => {
    async function fetchAiConfig() {
      try {
        const { data } = await api.get<AIConfig>("/v1/org/ai-config");
        setAiConfig(data);
        if (data.provider) setAiProvider(data.provider);
        if (data.model) {
          setAiModel(data.model);
        } else {
          setAiModel(DEFAULT_MODELS[data.provider || "openai"] || "gpt-4o-mini");
        }
        if (data.api_key) {
          setAiApiKey(data.api_key);
          setOriginalApiKey(data.api_key);
        }
        if (data.base_url) setAiBaseUrl(data.base_url);
        if (data.embedding_provider) setAiEmbeddingProvider(data.embedding_provider);
        if (data.embedding_model) setAiEmbeddingModel(data.embedding_model);
      } catch {
        // silently handle
      } finally {
        setLoadingAi(false);
      }
    }
    fetchAiConfig();
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

  function handleProviderChange(newProvider: string) {
    setAiProvider(newProvider);
    // Auto-fill default model when provider changes (only if model is empty or was a default)
    const currentDefault = DEFAULT_MODELS[aiProvider];
    if (!aiModel || aiModel === currentDefault) {
      setAiModel(DEFAULT_MODELS[newProvider] || "");
    }
  }

  function handleEmbeddingProviderChange(newProvider: string) {
    setAiEmbeddingProvider(newProvider);
    const currentDefault = DEFAULT_EMBEDDING_MODELS[aiEmbeddingProvider];
    if (!aiEmbeddingModel || aiEmbeddingModel === currentDefault) {
      setAiEmbeddingModel(DEFAULT_EMBEDDING_MODELS[newProvider] || "");
    }
  }

  async function handleSaveAi(e: FormEvent) {
    e.preventDefault();
    setSavingAi(true);
    try {
      const payload: Record<string, string | null> = {};

      if (aiProvider !== (aiConfig.provider || "openai")) payload.provider = aiProvider;
      if (aiModel !== (aiConfig.model || "")) payload.model = aiModel;
      if (aiApiKey !== originalApiKey) payload.api_key = aiApiKey;
      if (aiProvider === "ollama") {
        if (aiBaseUrl !== (aiConfig.base_url || "")) payload.base_url = aiBaseUrl || null;
      } else {
        if (aiConfig.base_url) payload.base_url = null;
      }
      if (aiEmbeddingProvider !== (aiConfig.embedding_provider || "openai"))
        payload.embedding_provider = aiEmbeddingProvider;
      if (aiEmbeddingModel !== (aiConfig.embedding_model || ""))
        payload.embedding_model = aiEmbeddingModel;

      // Always send provider and model so backend validation works
      if (!payload.provider) payload.provider = aiProvider;
      if (!payload.model) payload.model = aiModel || DEFAULT_MODELS[aiProvider] || "gpt-4o-mini";
      if (aiProvider === "ollama" && !payload.base_url) payload.base_url = aiBaseUrl;

      const { data } = await api.patch<AIConfig>("/v1/org/ai-config", payload);
      setAiConfig(data);
      if (data.api_key) {
        setAiApiKey(data.api_key);
        setOriginalApiKey(data.api_key);
      }
      setShowApiKey(false);
      toast({ title: "Saved", description: "AI configuration updated." });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to update AI configuration.";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setSavingAi(false);
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

      <Card>
        <CardHeader>
          <CardTitle>AI Configuration</CardTitle>
          <CardDescription>
            Configure the AI provider and models for your organization.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loadingAi ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <form onSubmit={handleSaveAi} className="space-y-4">
              {/* Provider */}
              <div className="space-y-2">
                <label htmlFor="aiProvider" className="text-sm font-medium">
                  Provider
                </label>
                <select
                  id="aiProvider"
                  value={aiProvider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  disabled={!isAdmin}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="openai">OpenAI</option>
                  <option value="groq">Groq</option>
                  <option value="ollama">Ollama</option>
                </select>
              </div>

              {/* Model */}
              <div className="space-y-2">
                <label htmlFor="aiModel" className="text-sm font-medium">
                  Model
                </label>
                <Input
                  id="aiModel"
                  value={aiModel}
                  onChange={(e) => setAiModel(e.target.value)}
                  placeholder={DEFAULT_MODELS[aiProvider] || "Model name"}
                  disabled={!isAdmin}
                />
              </div>

              {/* API Key — hidden for Ollama */}
              {aiProvider !== "ollama" && (
                <div className="space-y-2">
                  <label htmlFor="aiApiKey" className="text-sm font-medium">
                    API Key
                  </label>
                  <div className="flex gap-2">
                    <Input
                      id="aiApiKey"
                      type={showApiKey ? "text" : "password"}
                      value={aiApiKey}
                      onChange={(e) => setAiApiKey(e.target.value)}
                      placeholder="Enter API key"
                      disabled={!isAdmin}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="shrink-0"
                    >
                      {showApiKey ? "🔒" : "👁"}
                    </Button>
                  </div>
                </div>
              )}

              {/* Ollama Server URL */}
              {aiProvider === "ollama" && (
                <div className="space-y-2">
                  <label htmlFor="aiBaseUrl" className="text-sm font-medium">
                    Ollama Server URL
                  </label>
                  <Input
                    id="aiBaseUrl"
                    value={aiBaseUrl}
                    onChange={(e) => setAiBaseUrl(e.target.value)}
                    placeholder="http://localhost:11434"
                    disabled={!isAdmin}
                  />
                </div>
              )}

              <Separator />

              {/* Embedding Provider */}
              <div className="space-y-2">
                <label htmlFor="aiEmbeddingProvider" className="text-sm font-medium">
                  Embedding Provider
                </label>
                <select
                  id="aiEmbeddingProvider"
                  value={aiEmbeddingProvider}
                  onChange={(e) => handleEmbeddingProviderChange(e.target.value)}
                  disabled={!isAdmin}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama</option>
                </select>
              </div>

              {/* Embedding Model */}
              <div className="space-y-2">
                <label htmlFor="aiEmbeddingModel" className="text-sm font-medium">
                  Embedding Model
                </label>
                <Input
                  id="aiEmbeddingModel"
                  value={aiEmbeddingModel}
                  onChange={(e) => setAiEmbeddingModel(e.target.value)}
                  placeholder={DEFAULT_EMBEDDING_MODELS[aiEmbeddingProvider] || "Embedding model name"}
                  disabled={!isAdmin}
                />
              </div>

              {isAdmin && (
                <Button type="submit" disabled={savingAi}>
                  {savingAi ? "Saving…" : "Save AI Configuration"}
                </Button>
              )}
              {!isAdmin && (
                <p className="text-xs text-muted-foreground">
                  Only admins can edit AI configuration.
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

