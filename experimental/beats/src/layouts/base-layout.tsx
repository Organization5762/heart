import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import React, { useEffect, useState, useTransition } from "react";
import { getAppVersion } from "../actions/app";
import { AppSidebar } from "../components/app-sidebar";

export default function BaseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [appVersion, setAppVersion] = useState("0.0.0");
  const [, startGetAppVersion] = useTransition();

  useEffect(
    () => startGetAppVersion(() => getAppVersion().then(setAppVersion)),
    [],
  );

  return (
    <SidebarProvider>
      <div className="border-border bg-background/95 fixed inset-x-0 top-0 z-[15] flex h-[38px] items-center border-b px-16 backdrop-blur-sm [-webkit-app-region:drag]">
        <div className="font-tomorrow text-muted-foreground flex items-center gap-3 text-[0.62rem] tracking-[0.32em] uppercase">
          <span className="hidden sm:inline">U.S. Graphics Company</span>
          <span className="text-border hidden sm:inline">/</span>
          <span>Beats Telemetry Terminal</span>
        </div>
        <div className="ml-auto flex items-center gap-2 [-webkit-app-region:no-drag]">
          <span className="border-border bg-card text-muted-foreground hidden rounded-[3px] border px-2 py-1 font-mono text-[0.68rem] tracking-[0.18em] uppercase md:inline-flex">
            v{appVersion}
          </span>
          <SidebarTrigger className="border-border bg-card text-foreground hover:bg-primary border" />
        </div>
      </div>
      <AppSidebar />
      <SidebarInset className="mt-[38px]">
        <div className="h-full overflow-y-auto">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
