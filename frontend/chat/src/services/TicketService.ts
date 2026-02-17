// Is file ka kaam sirf Case Number dena hai
export class TicketService {
  static async generateMockCase(): Promise<string> {
    // Thoda delay taaki real feeling aaye
    await new Promise(res => setTimeout(res, 1000));
    
    // Salesforce style 8-digit random number
    const randomID = Math.floor(10000000 + Math.random() * 90000000);
    return `00${String(randomID).substring(0, 6)}`;
  }
}