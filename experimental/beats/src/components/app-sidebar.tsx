import {
  ChevronRight,
  Home,
  Monitor,
  Mouse,
  RadioTower,
  Tv,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Link, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, useTransition } from "react";
import { getAppVersion } from "../actions/app";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./ui/collapsible";
import { DataRow, SpecChip } from "./usgc";
import {
  SidebarFooter,
  SidebarHeader,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "./ui/sidebar";

// Menu items.
const items = {
  topLevel: [
    {
      title: "Home",
      url: "/",
      icon: Home,
    },
    {
      title: "Current Stream",
      url: "/stream",
      icon: Tv,
    },
  ],
  navMain: [
    {
      title: "Display",
      icon: Monitor,
      items: [
        {
          title: "View",
          url: "/",
        },
      ],
    },
    {
      title: "Peripherals",
      icon: Mouse,
      isActive: true,
      items: [
        {
          title: "Connected",
          url: "/peripherals/connected",
        },
        {
          title: "Events",
          url: "/peripherals/events",
        },
        {
          title: "Snapshots",
          url: "/peripherals/snapshots",
        },
      ],
    },
  ],
};

export function AppSidebar() {
  const [appVersion, setAppVersion] = useState("0.0.0");
  const [, startGetAppVersion] = useTransition();
  const { open } = useSidebar();
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });

  useEffect(
    () => startGetAppVersion(() => getAppVersion().then(setAppVersion)),
    [],
  );

  const isPathActive = (path: string) =>
    path === "/"
      ? pathname === path
      : pathname === path || pathname.startsWith(`${path}/`);

  return (
    <Sidebar collapsible="icon" variant="floating" className="pt-[38px]">
      <SidebarHeader className="gap-3 p-3">
        <div className="border-sidebar-border bg-sidebar overflow-hidden border p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-2">
              <p className="font-tomorrow text-sidebar-foreground/60 text-[0.58rem] tracking-[0.34em] uppercase">
                U.S. Graphics Company
              </p>
              <div>
                <h2 className="font-tomorrow text-sidebar-foreground text-lg tracking-[0.2em]">
                  BEATS
                </h2>
                <p className="text-sidebar-foreground/70 font-mono text-[0.68rem] tracking-[0.16em] uppercase">
                  Telemetry Department
                </p>
              </div>
            </div>
            <SpecChip className="px-2 py-0.5 text-[0.62rem]">TX-24</SpecChip>
          </div>
          <div className="mt-4 grid gap-2 group-data-[collapsible=icon]:hidden">
            <DataRow
              label="Program"
              value="Machine Report"
              className="text-sidebar-foreground"
            />
            <DataRow
              label="Signal"
              value="ws://localhost:8765"
              className="text-sidebar-foreground"
            />
          </div>
        </div>
      </SidebarHeader>
      <SidebarSeparator className="mx-3" />
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {items.topLevel.map((item) => (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  asChild
                  tooltip={item.title}
                  isActive={isPathActive(item.url)}
                  className="font-tomorrow tracking-[0.16em] uppercase"
                >
                  <Link to={item.url}>
                    {item.icon && <item.icon />}
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel className="font-tomorrow tracking-[0.18em] uppercase">
            Entities
          </SidebarGroupLabel>
          <SidebarMenu>
            {items.navMain.map((item) => (
              <Collapsible
                key={item.title}
                asChild
                defaultOpen={item.isActive}
                className="group/collapsible"
              >
                <SidebarMenuItem>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton
                      tooltip={item.title}
                      isActive={item.items.some((subItem) =>
                        isPathActive(subItem.url),
                      )}
                      className="font-tomorrow tracking-[0.16em] uppercase"
                    >
                      {item.icon && <item.icon />}
                      <span>{item.title}</span>
                      <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <SidebarMenuSub>
                      {item.items?.map((subItem) => (
                        <SidebarMenuSubItem key={subItem.title}>
                          <SidebarMenuSubButton
                            asChild
                            isActive={isPathActive(subItem.url)}
                          >
                            <Link to={subItem.url}>
                              <span>{subItem.title}</span>
                            </Link>
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>
                      ))}
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </SidebarMenuItem>
              </Collapsible>
            ))}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarFooter>
          <div
            className={`border-sidebar-border grid gap-2 border-t px-2 pt-3 pb-1 transition-all duration-100 ${
              open
                ? "translate-x-0 opacity-100"
                : "pointer-events-none -translate-x-6 opacity-0"
            }`}
          >
            <div className="text-sidebar-foreground/70 flex items-center gap-2 text-[0.65rem] tracking-[0.18em] uppercase">
              <RadioTower className="size-3" />
              <span>House Styles</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <SpecChip
                tone="muted"
                className="bg-sidebar px-2 py-0.5 text-[0.62rem]"
              >
                TR-100
              </SpecChip>
              <SpecChip
                tone="muted"
                className="bg-sidebar px-2 py-0.5 text-[0.62rem]"
              >
                Houston Mono
              </SpecChip>
            </div>
            <p className="text-sidebar-foreground/60 font-mono text-[0.68rem] tracking-[0.18em] uppercase">
              Version {appVersion}
            </p>
          </div>
        </SidebarFooter>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  );
}
