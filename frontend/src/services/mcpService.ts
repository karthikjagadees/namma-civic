import api from './api';

export interface MCPTool {
  name: string;
  description: string;
  category: string;
  parameters: any;
  returns: any;
}

export interface MCPToolListResponse {
  jsonrpc: string;
  tools: MCPTool[];
}

export const mcpService = {
  async listTools(category?: string): Promise<MCPTool[]> {
    const url = category ? `/mcp/tools?category=${category}` : '/mcp/tools';
    const res = await api.get<MCPToolListResponse>(url);
    return res.data.tools;
  },

  async invokeTool(toolName: string, args: Record<string, any>): Promise<any> {
    const res = await api.post(`/mcp/invoke/${toolName}`, {
      arguments: args,
    });
    return res.data;
  },
};
