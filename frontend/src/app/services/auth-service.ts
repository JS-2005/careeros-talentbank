import { Injectable } from '@angular/core';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private supabase: SupabaseClient;

  constructor() {
    this.supabase = createClient(environment.supabaseUrl, environment.supabaseKey);
  }

  get supabaseClient(): SupabaseClient {
    return this.supabase;
  }

  private currentUser: any = null;

  async signInWithGoogle() {
    this.currentUser = null;
    const { data, error } = await this.supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/internal`
      }
    });
    
    if (error) throw error;
    
    return data;
  }

  async getUser() {
    if (this.currentUser) {
      return this.currentUser;
    }
    const { data, error } = await this.supabase.auth.getUser(); 

    if(error || !data?.user) return null; 

    this.currentUser = data.user;
    return data.user; 
  }
  
  async signOut() {
    this.currentUser = null;
    const { error } = await this.supabase.auth.signOut(); 

    if (error) throw error; 
  }
  
}