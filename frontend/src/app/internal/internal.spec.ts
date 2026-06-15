import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Internal } from './internal';

describe('Internal', () => {
  let component: Internal;
  let fixture: ComponentFixture<Internal>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Internal],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(Internal);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
