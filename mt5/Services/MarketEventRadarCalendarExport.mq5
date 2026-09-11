#property service
#property copyright "futurenowchen"
#property link      "https://github.com/futurenowchen/market-event-radar"
#property version   "1.00"
#property description "Private/local MetaTrader 5 Economic Calendar canary exporter."

input int    PollSeconds        = 60;
input int    LookbackHours      = 48;
input int    LookaheadDays      = 14;
input string CountryCode        = "US";
input string CurrencyCode       = "USD";
input string RelativeOutputPath = "MarketEventRadar\\mt5_calendar_latest.json";

string JsonEscape(string value)
  {
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r","\\r");
   StringReplace(value,"\n","\\n");
   StringReplace(value,"\t","\\t");
   return value;
  }

string JsonString(const string value)
  {
   return "\""+JsonEscape(value)+"\"";
  }

string IsoDateTime(const datetime value)
  {
   MqlDateTime parts={};
   TimeToStruct(value,parts);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d",
                       parts.year,parts.mon,parts.day,
                       parts.hour,parts.min,parts.sec);
  }

string ULongString(const ulong value)
  {
   return StringFormat("%I64u",value);
  }

string OptionalValue(const bool available,const double value,const uint digits)
  {
   if(!available)
      return "null";
   int precision=(int)MathMin((double)digits,12.0);
   return DoubleToString(value,precision);
  }

bool IsCanarySector(const MqlCalendarEvent &event)
  {
   if(event.type!=CALENDAR_TYPE_INDICATOR)
      return false;
   return event.sector==CALENDAR_SECTOR_PRICES || event.sector==CALENDAR_SECTOR_JOBS;
  }

bool WriteExport()
  {
   const datetime capture_server=TimeTradeServer();
   const datetime capture_gmt=TimeGMT();
   const long server_utc_offset_seconds=(long)(capture_server-capture_gmt);
   const datetime window_from=capture_server-(datetime)(MathMax(LookbackHours,0)*3600);
   const datetime window_to=capture_server+(datetime)(MathMax(LookaheadDays,1)*86400);

   MqlCalendarValue values[];
   ResetLastError();
   const int total=CalendarValueHistory(values,window_from,window_to,CountryCode,CurrencyCode);
   if(total<0)
     {
      PrintFormat("MarketEventRadar calendar query failed: error=%d",GetLastError());
      return false;
     }

   const string temp_path=RelativeOutputPath+".tmp";
   ResetLastError();
   const int handle=FileOpen(temp_path,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("MarketEventRadar export open failed: error=%d path=%s",GetLastError(),temp_path);
      return false;
     }

   FileWriteString(handle,"{\n");
   FileWriteString(handle,"  \"schema_version\": 1,\n");
   FileWriteString(handle,"  \"provider\": \"metatrader5-economic-calendar\",\n");
   FileWriteString(handle,"  \"capture_time_server\": "+JsonString(IsoDateTime(capture_server))+",\n");
   FileWriteString(handle,"  \"capture_time_gmt\": "+JsonString(IsoDateTime(capture_gmt))+",\n");
   FileWriteString(handle,"  \"server_utc_offset_seconds\": "+(string)server_utc_offset_seconds+",\n");
   FileWriteString(handle,"  \"terminal_language\": "+JsonString(TerminalInfoString(TERMINAL_LANGUAGE))+",\n");
   FileWriteString(handle,"  \"terminal_name\": "+JsonString(TerminalInfoString(TERMINAL_NAME))+",\n");
   FileWriteString(handle,"  \"terminal_company\": "+JsonString(TerminalInfoString(TERMINAL_COMPANY))+",\n");
   FileWriteString(handle,"  \"country_code\": "+JsonString(CountryCode)+",\n");
   FileWriteString(handle,"  \"currency\": "+JsonString(CurrencyCode)+",\n");
   FileWriteString(handle,"  \"window_from_server\": "+JsonString(IsoDateTime(window_from))+",\n");
   FileWriteString(handle,"  \"window_to_server\": "+JsonString(IsoDateTime(window_to))+",\n");
   FileWriteString(handle,"  \"rows\": [\n");

   int written=0;
   for(int i=0;i<total;i++)
     {
      MqlCalendarEvent event={};
      ResetLastError();
      if(!CalendarEventById(values[i].event_id,event))
        {
         PrintFormat("MarketEventRadar event lookup failed: event_id=%s error=%d",
                     ULongString(values[i].event_id),GetLastError());
         continue;
        }
      if(!IsCanarySector(event))
         continue;

      if(written>0)
         FileWriteString(handle,",\n");

      FileWriteString(handle,"    {\n");
      FileWriteString(handle,"      \"provider_event_id\": "+JsonString(ULongString(event.id))+",\n");
      FileWriteString(handle,"      \"provider_value_id\": "+JsonString(ULongString(values[i].id))+",\n");
      FileWriteString(handle,"      \"event_code\": "+JsonString(event.event_code)+",\n");
      FileWriteString(handle,"      \"event_name\": "+JsonString(event.name)+",\n");
      FileWriteString(handle,"      \"sector\": "+JsonString(EnumToString(event.sector))+",\n");
      FileWriteString(handle,"      \"importance\": "+JsonString(EnumToString(event.importance))+",\n");
      FileWriteString(handle,"      \"unit\": "+JsonString(EnumToString(event.unit))+",\n");
      FileWriteString(handle,"      \"multiplier\": "+JsonString(EnumToString(event.multiplier))+",\n");
      FileWriteString(handle,"      \"digits\": "+(string)event.digits+",\n");
      FileWriteString(handle,"      \"source_url\": "+JsonString(event.source_url)+",\n");
      FileWriteString(handle,"      \"release_time_server\": "+JsonString(IsoDateTime(values[i].time))+",\n");
      FileWriteString(handle,"      \"period_server\": "+JsonString(IsoDateTime(values[i].period))+",\n");
      FileWriteString(handle,"      \"forecast\": "+OptionalValue(values[i].HasForecastValue(),values[i].GetForecastValue(),event.digits)+",\n");
      FileWriteString(handle,"      \"previous\": "+OptionalValue(values[i].HasPreviousValue(),values[i].GetPreviousValue(),event.digits)+",\n");
      FileWriteString(handle,"      \"revised_previous\": "+OptionalValue(values[i].HasRevisedValue(),values[i].GetRevisedValue(),event.digits)+",\n");
      FileWriteString(handle,"      \"actual\": "+OptionalValue(values[i].HasActualValue(),values[i].GetActualValue(),event.digits)+"\n");
      FileWriteString(handle,"    }");
      written++;
     }

   FileWriteString(handle,"\n  ],\n");
   FileWriteString(handle,"  \"row_count\": "+(string)written+"\n");
   FileWriteString(handle,"}\n");
   FileFlush(handle);
   FileClose(handle);

   ResetLastError();
   if(!FileMove(temp_path,FILE_COMMON,RelativeOutputPath,FILE_COMMON|FILE_REWRITE))
     {
      PrintFormat("MarketEventRadar atomic export move failed: error=%d",GetLastError());
      return false;
     }

   PrintFormat("MarketEventRadar MT5 canary export wrote %d rows to %s\\Files\\%s",
               written,TerminalInfoString(TERMINAL_COMMONDATA_PATH),RelativeOutputPath);
   return true;
  }

void OnStart()
  {
   const int poll_seconds=(int)MathMax(30,MathMin(PollSeconds,3600));
   Print("MarketEventRadar MT5 calendar export service started");
   while(!IsStopped())
     {
      WriteExport();
      for(int elapsed=0;elapsed<poll_seconds && !IsStopped();elapsed++)
         Sleep(1000);
     }
   Print("MarketEventRadar MT5 calendar export service stopped");
  }
