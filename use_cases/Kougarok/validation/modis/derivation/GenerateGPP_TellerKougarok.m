clear;clc;
% sitenm='Teller';
sitenm='Kougarok';

% [tmpdata,txt,raw] = xlsread('./TellerKougarokGPP/TellerKougarok-MYD17A2HGF-061-results_Teller.xlsx');
[tmpdata,txt,raw] = xlsread(['./TellerKougarokGPP/TellerKougarok-MYD17A2HGF-061-results_',sitenm,'.xlsx']);

field_id=10;%GPP field, kgC/m^2/8day, MYD17A2HGF_061_Gpp_500m
factor=1000/8.0; %convert to C/m^2/day

yearlis=2002:2023;
n=1;m=1;
for iyear=yearlis
    for imon=1:12
             
        for iday=1:eomday(iyear,imon)
            
                LAI_daily(n,1)=iyear;
                LAI_daily(n,2)=imon;
                LAI_daily(n,3)=iday;
                
                id=find(tmpdata(:,4)==iyear&tmpdata(:,5)==imon&tmpdata(:,6)==iday);
                if ~isempty(id)
                LAI_daily(n,4)=tmpdata(id,field_id);
                else
                LAI_daily(n,4)=NaN;   
                end
                
                n=n+1;
        end
        
    end
end
LAI_daily(:,4)=LAI_daily(:,4)*factor;%C/m^2/day
data_daily=[];
for iyear=yearlis
    data_tmp=LAI_daily(LAI_daily(:,1)==iyear,:);
for kk=1:8:size(data_tmp,1) %8-day product
    data_tmp((kk+1):min(kk+7,size(data_tmp,1)),4)=data_tmp(kk,4);
end
    data_daily=[data_daily',data_tmp']';
end

GPP_daily=data_daily;
% GPP_daily(:,4)=movingmedian_days(data_daily(:,4),4);
GPP_monthly=monthlyavg(GPP_daily,GPP_daily(:,1:3),yearlis,10);

save([sitenm,'_MODISGPP_2002to2023.mat'],'GPP_daily','GPP_monthly');

plot(GPP_monthly(:,end),'LineWidth',3);
set(gca,'xtick',1:24*2:264,'xticklabel',GPP_monthly(1:24*2:264,1))
set(gca,'FontWeight','bold','FontSize',22,'LineWidth',1.5);
ylabel('MODIS GPP (C m^{-2} day^{-1})','FontWeight','bold','FontSize',22);


