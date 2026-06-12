import { Component, inject } from '@angular/core'; 
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from '@angular/router';
import { AuthService } from '../services/auth-service';

@Component({
  selector: 'app-internal',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './internal.html',
  styleUrl: './internal.css',
})
export class Internal {
  private router = inject(Router); 
  isSidebarOpen = false;

  constructor(private authService: AuthService){}; 
  
  toggleSidebar() {
    this.isSidebarOpen = !this.isSidebarOpen;
  }

  closeSidebar() {
    this.isSidebarOpen = false;
  }

  async signOut() {
    try {
      await this.authService.signOut(); 
      this.router.navigate([''], { replaceUrl: true })
    } catch(error) {
      alert('Logout failed: '+error); 
    }
  }; 
}
