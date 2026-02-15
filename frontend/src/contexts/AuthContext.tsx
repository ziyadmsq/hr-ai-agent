import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

interface Org {
  id: string;
  name: string;
  slug: string;
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  org: Org | null;
  isAuthenticated: boolean;
  login: (token: string, user: User, org: Org) => void;
  logout: () => void;
  setOrg: (org: Org) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function getStoredValue<T>(key: string): T | null {
  try {
    const item = localStorage.getItem(key);
    return item ? (JSON.parse(item) as T) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("access_token")
  );
  const [user, setUser] = useState<User | null>(
    () => getStoredValue<User>("user")
  );
  const [org, setOrgState] = useState<Org | null>(
    () => getStoredValue<Org>("org")
  );

  const login = useCallback((newToken: string, newUser: User, newOrg: Org) => {
    localStorage.setItem("access_token", newToken);
    localStorage.setItem("user", JSON.stringify(newUser));
    localStorage.setItem("org", JSON.stringify(newOrg));
    setToken(newToken);
    setUser(newUser);
    setOrgState(newOrg);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    localStorage.removeItem("org");
    setToken(null);
    setUser(null);
    setOrgState(null);
  }, []);

  const setOrg = useCallback((newOrg: Org) => {
    localStorage.setItem("org", JSON.stringify(newOrg));
    setOrgState(newOrg);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        org,
        isAuthenticated: !!token,
        login,
        logout,
        setOrg,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

