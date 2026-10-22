function [RailNodes_LSR, RailNodes_LDR, RailNodes_RSR, RailNodes_RDR, RailNodes_LCR, RailNodes_RCR, ...
          RailNodes_num_v1, RailNodes_pos_v1] = Get_FEM_Rail_P1_Through(Density)

% Beam properities
% 1-Area, A.
% 2-Moment of inertia for bending about the 1-axis, I11.（竖直轴）
% 3-Moment of inertia for cross bending, I12.
% 4-Moment of inertia for bending about the 2-axis, I22.（水平轴）
% 5-Torsional constant, J.
% 6-Young's modulus, E.
% 7-Torsional shear modulus, G.

%% ===================== 读取道岔FEM模型节点
load AbaqusInput
load AbaqusInputTrackExtension

for i = 1:1:size(RailNodes,1)
    for j = 1:1:size(RailNodes,2)
        pos = RailNodes(i,j).location;
        if ~isempty(pos)
            RailNodes_num(i,j) = RailNodes(i,j).number;
            RailNodes_Dnum(i,j) = RailNodes(i,j).DNnumber;
            RailNodes_pos{i,j} = [pos(1) pos(2) pos(3)];
        end
    end
end

for i = 1:1:size(RailNodesTrackExtension,1)
    for j = 1:1:size(RailNodesTrackExtension,2)
        RailNodesTrackExtension(i,j).location(1) = RailNodesTrackExtension(i,j).location(1)-25.2;
        RailNodesTrackExtension(i,j).DNlocation(1) = RailNodesTrackExtension(i,j).DNlocation(1)-25.2;
        if j == 1
            RailNodesTrackExtension(i,j).body = 'LSR_Ext';
        elseif j == 2
            RailNodesTrackExtension(i,j).body = 'RSR_Ext';
        end
        pos = RailNodesTrackExtension(i,j).location;
        if ~isempty(pos)
            RailNodesTrackExtension_num(i,j) = RailNodesTrackExtension(i,j).number;
            RailNodesTrackExtension_Dnum(i,j) = RailNodesTrackExtension(i,j).DNnumber;
            RailNodesTrackExtension_pos{i,j} = [pos(1) pos(2) pos(3)];
        end
    end
end

RailNodes_num_v1 = RailNodes_num;
RailNodes_pos_v1 = RailNodes_pos;

RailNodes_bools = zeros(size(RailNodes_num));
RailNodes_LSR = [];
RailNodes_LDR = [];
RailNodes_RSR = [];
RailNodes_RDR = [];
RailNodes_LCR = [];
RailNodes_RCR = [];

%% LSR, kk = 1
% Node positions
kk = 1;

fid = fopen('RailSectionSI_LSR.inp');
pos_node_temp_1 = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);

pos_node = [pos_node_temp_1{1,1} pos_node_temp_1{1,2} pos_node_temp_1{1,3} pos_node_temp_1{1,4}];

for i = 1:2:length(pos_node)
    p = find(abs(RailNodes_num(:,kk)-pos_node(i,1))<1e-5);
    RailNodes_LSR = [RailNodes_LSR; RailNodes(p,kk)];
    RailNodes_bools(p,kk) = 1;
end
RailNodes_LSR = [RailNodesTrackExtension(1:end-1,1); RailNodes_LSR];

% Beam properities
fid = fopen('RailSectionSI_LSR.inp');
beam_properities_1 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',1240,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

for k = 1:1:length(RailNodes_LSR)-1
    RailNodes_LSR(k,1).Area = beam_properities_1{1,1};
    RailNodes_LSR(k,1).I11 = beam_properities_1{1,2};
    RailNodes_LSR(k,1).I12 = beam_properities_1{1,3};
    RailNodes_LSR(k,1).I22 = beam_properities_1{1,4};
    RailNodes_LSR(k,1).TorsionalConstant = beam_properities_1{1,5};
    RailNodes_LSR(k,1).YoungModulus = beam_properities_1{1,6};
    RailNodes_LSR(k,1).ShearModulus = beam_properities_1{1,7};
end

% for k = 1:1:length(RailNodes_LSR)-1
%     loc = [RailNodes_LSR(k,1).location; RailNodes_LSR(k+1,1).location];
%     RailNodes_LSR(k,1).Length = sqrt((loc(2,1)-loc(1,1))^2+(loc(2,2)-loc(1,2))^2+(loc(2,3)-loc(1,3))^2);
%     RailNodes_LSR(k,1).Mass = RailNodes_LSR(k,1).Area * RailNodes_LSR(k,1).Length * Density;
% end

%% LDR, kk = 2
% Node positions
kk = 2;

fid = fopen('RailSectionSI_LDR_1.inp');
pos_node_temp_1 = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);
fid = fopen('RailSectionSI_LDR_3.inp');
pos_node_temp_3 = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);

pos_node = [pos_node_temp_1{1,1} pos_node_temp_1{1,2} pos_node_temp_1{1,3} pos_node_temp_1{1,4};...
            pos_node_temp_3{1,1} pos_node_temp_3{1,2} pos_node_temp_3{1,3} pos_node_temp_3{1,4}];

for i = 1:2:length(pos_node)
    p = find(abs(RailNodes_num(:,kk)-pos_node(i,1))<1e-5);
    RailNodes_LDR = [RailNodes_LDR; RailNodes(p,kk)];    
    RailNodes_bools(p,kk) = 1;
end

% Beam properities
fid = fopen('RailSectionSI_LDR_1.inp');
beam_properities_1 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',1175,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

fid = fopen('RailSectionSI_LDR_3.inp');
beam_properities_3 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',226,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

beam_properities_1 = [beam_properities_1{1,1} beam_properities_1{1,2} beam_properities_1{1,3} beam_properities_1{1,4}...
                      beam_properities_1{1,5} beam_properities_1{1,6} beam_properities_1{1,7} ];
beam_properities_3 = [beam_properities_3{1,1} beam_properities_3{1,2} beam_properities_3{1,3} beam_properities_3{1,4}...
                      beam_properities_3{1,5} beam_properities_3{1,6} beam_properities_3{1,7} ]; 
                  
p = [1 0 length(beam_properities_1)+2];
q = [length(beam_properities_1) 0 length(RailNodes_LDR)-1];
for i = 1:2:3
    for k = p(i):1:q(i)
        if i == 1
            kk = k;
        else
            kk = 1;
        end
        RailNodes_LDR(k,1).Area = eval(['beam_properities_',num2str(i),'(kk,1);']);
        RailNodes_LDR(k,1).I11 = eval(['beam_properities_',num2str(i),'(kk,2);']);
        RailNodes_LDR(k,1).I12 = eval(['beam_properities_',num2str(i),'(kk,3);']);
        RailNodes_LDR(k,1).I22 = eval(['beam_properities_',num2str(i),'(kk,4);']);
        RailNodes_LDR(k,1).TorsionalConstant = eval(['beam_properities_',num2str(i),'(kk,5);']);
        RailNodes_LDR(k,1).YoungModulus = eval(['beam_properities_',num2str(i),'(kk,6);']);
        RailNodes_LDR(k,1).ShearModulus = eval(['beam_properities_',num2str(i),'(kk,7);']);
    end
end

% for k = 1:1:length(RailNodes_LDR)-1
%     if ~isempty(RailNodes_LDR(k,1).Area)
%         loc = [RailNodes_LDR(k,1).location; RailNodes_LDR(k+1,1).location];
%         RailNodes_LDR(k,1).Length = sqrt((loc(2,1)-loc(1,1))^2+(loc(2,2)-loc(1,2))^2+(loc(2,3)-loc(1,3))^2);
%         RailNodes_LDR(k,1).Mass = RailNodes_LDR(k,1).Area * RailNodes_LDR(k,1).Length * Density;
%     end
% end

%% RSR, kk = 3,5
% Node positions
fid = fopen('RailSectionSI_RSR_1.inp');
pos_node_temp_1    = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);

fid = fopen('RailSectionSI_CR.inp');
pos_node_temp_2 = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);

fid = fopen('RailSectionSI_RSR_3.inp');
pos_node_temp_3 = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);

len_1 = length(pos_node_temp_1{1,1});
len_2 = length(pos_node_temp_2{1,1});
len_3 = length(pos_node_temp_3{1,1});
CR_start = pos_node_temp_2{1,2}(1);
CR_end = pos_node_temp_2{1,2}(end);

pos_node = [pos_node_temp_1{1,1} pos_node_temp_1{1,2} pos_node_temp_1{1,3} pos_node_temp_1{1,4};...
            pos_node_temp_2{1,1} pos_node_temp_2{1,2} pos_node_temp_2{1,3} pos_node_temp_2{1,4};...
            pos_node_temp_3{1,1} pos_node_temp_3{1,2} pos_node_temp_3{1,3} pos_node_temp_3{1,4}];
pos_node([len_1-1:len_1 len_1+len_2+1:len_1+len_2+2],:) = [];

for i = 1:2:length(pos_node)
    if pos_node(i,2) >= CR_start && pos_node(i,2) <= CR_end
        kk = 5;
    else
        kk = 3;
    end
    p = find(abs(RailNodes_num(:,kk)-pos_node(i,1))<1e-5);
    RailNodes_RSR = [RailNodes_RSR; RailNodes(p,kk)];    
    RailNodes_bools(p,kk) = 1;
end

% Beam properities
fid = fopen('RailSectionSI_RSR_1.inp');
beam_properities_1 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',1175,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

fid = fopen('RailSectionSI_CR.inp');
beam_properities_2 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',124,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

fid = fopen('RailSectionSI_RSR_3.inp');
beam_properities_3 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',226,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

beam_properities_1 = [beam_properities_1{1,1} beam_properities_1{1,2} beam_properities_1{1,3} beam_properities_1{1,4}...
                      beam_properities_1{1,5} beam_properities_1{1,6} beam_properities_1{1,7} ];
beam_properities_2 = [beam_properities_2{1,1} beam_properities_2{1,2} beam_properities_2{1,3} beam_properities_2{1,4}...
                      beam_properities_2{1,5} beam_properities_2{1,6} beam_properities_2{1,7} ];
beam_properities_3 = [beam_properities_3{1,1} beam_properities_3{1,2} beam_properities_3{1,3} beam_properities_3{1,4}...
                      beam_properities_3{1,5} beam_properities_3{1,6} beam_properities_3{1,7} ];                 

p = [1 (len_1-2)/2+1 (len_1-2)/2+len_2/2];
q = [length(beam_properities_1) (len_1-2)/2+len_2/2-1 (len_1-2)/2+len_2/2+len_3/2-2];
for i = 1:1:3
    for k = p(i):1:q(i)
        if i == 1
            kk = k;
        else
            kk = 1;
        end
        RailNodes_RSR(k,1).Area = eval(['beam_properities_',num2str(i),'(kk,1);']);
        RailNodes_RSR(k,1).I11 = eval(['beam_properities_',num2str(i),'(kk,2);']);
        RailNodes_RSR(k,1).I12 = eval(['beam_properities_',num2str(i),'(kk,3);']);
        RailNodes_RSR(k,1).I22 = eval(['beam_properities_',num2str(i),'(kk,4);']);
        RailNodes_RSR(k,1).TorsionalConstant = eval(['beam_properities_',num2str(i),'(kk,5);']);
        RailNodes_RSR(k,1).YoungModulus = eval(['beam_properities_',num2str(i),'(kk,6);']);
        RailNodes_RSR(k,1).ShearModulus = eval(['beam_properities_',num2str(i),'(kk,7);']);
    end
end

% for k = 1:1:length(RailNodes_RSR)-1
%     if ~isempty(RailNodes_RSR(k,1).Area)
%         loc = [RailNodes_RSR(k,1).location; RailNodes_RSR(k+1,1).location];
%         RailNodes_RSR(k,1).Length = sqrt((loc(2,1)-loc(1,1))^2+(loc(2,2)-loc(1,2))^2+(loc(2,3)-loc(1,3))^2);
%         RailNodes_RSR(k,1).Mass = RailNodes_RSR(k,1).Area * RailNodes_RSR(k,1).Length * Density;
%     end
% end

%% RDR, kk = 4
% Node positions
kk = 4;

fid = fopen('RailSectionSI_RDR.inp');
pos_node_temp_1 = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);

pos_node = [pos_node_temp_1{1,1} pos_node_temp_1{1,2} pos_node_temp_1{1,3} pos_node_temp_1{1,4}];

for i = 1:2:length(pos_node)
    p = find(abs(RailNodes_num(:,kk)-pos_node(i,1))<1e-5);
    RailNodes_RDR = [RailNodes_RDR; RailNodes(p,kk)];
    RailNodes_bools(p,kk) = 1;
end

RailNodes_RDR = [RailNodesTrackExtension(1:end-1,2); RailNodes_RDR];

% Beam properities
fid = fopen('RailSectionSI_RDR.inp');
beam_properities_1 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',1240,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

for k = 1:1:length(RailNodes_RDR)-1
    RailNodes_RDR(k,1).Area = beam_properities_1{1,1};
    RailNodes_RDR(k,1).I11 = beam_properities_1{1,2};
    RailNodes_RDR(k,1).I12 = beam_properities_1{1,3};
    RailNodes_RDR(k,1).I22 = beam_properities_1{1,4};
    RailNodes_RDR(k,1).TorsionalConstant = beam_properities_1{1,5};
    RailNodes_RDR(k,1).YoungModulus = beam_properities_1{1,6};
    RailNodes_RDR(k,1).ShearModulus = beam_properities_1{1,7};
end

% for k = 1:1:length(RailNodes_RDR)-1
%     if ~isempty(RailNodes_RDR(k,1).Area)
%         loc = [RailNodes_RDR(k,1).location; RailNodes_RDR(k+1,1).location];
%         RailNodes_RDR(k,1).Length = sqrt((loc(2,1)-loc(1,1))^2+(loc(2,2)-loc(1,2))^2+(loc(2,3)-loc(1,3))^2);
%         RailNodes_RDR(k,1).Mass = RailNodes_RDR(k,1).Area * RailNodes_RDR(k,1).Length * Density;
%     end
% end

%% LCR, kk = 6
% Node positions
kk = 6;

fid = fopen('RailSectionSI_LCR.inp');
pos_node_temp_1 = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);

pos_node = [pos_node_temp_1{1,1} pos_node_temp_1{1,2} pos_node_temp_1{1,3} pos_node_temp_1{1,4}];

for i = 1:2:length(pos_node)
    p = find(abs(RailNodes_num(:,kk)-pos_node(i,1))<1e-5);
    RailNodes_LCR = [RailNodes_LCR; RailNodes(p,kk)];
    RailNodes_bools(p,kk) = 1;
end

% Beam properities
fid = fopen('RailSectionSI_LCR.inp');
beam_properities_1 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',196,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

for k = 1:1:length(RailNodes_LCR)-1
    RailNodes_LCR(k,1).Area = beam_properities_1{1,1};
    RailNodes_LCR(k,1).I11 = beam_properities_1{1,2};
    RailNodes_LCR(k,1).I12 = beam_properities_1{1,3};
    RailNodes_LCR(k,1).I22 = beam_properities_1{1,4};
    RailNodes_LCR(k,1).TorsionalConstant = beam_properities_1{1,5};
    RailNodes_LCR(k,1).YoungModulus = beam_properities_1{1,6};
    RailNodes_LCR(k,1).ShearModulus = beam_properities_1{1,7};
end

% for k = 1:1:length(RailNodes_LCR)-1
%     if ~isempty(RailNodes_LCR(k,1).Area)
%         loc = [RailNodes_LCR(k,1).location; RailNodes_LCR(k+1,1).location];
%         RailNodes_LCR(k,1).Length = sqrt((loc(2,1)-loc(1,1))^2+(loc(2,2)-loc(1,2))^2+(loc(2,3)-loc(1,3))^2);
%         RailNodes_LCR(k,1).Mass = RailNodes_LCR(k,1).Area * RailNodes_LCR(k,1).Length * Density;
%     end
% end

%% RCR, kk = 7
% Node positions
kk = 7;

fid = fopen('RailSectionSI_RCR.inp');
pos_node_temp_1 = textscan(fid,'%f %f %f %f','HeaderLines',1,'Delimiter',',','MultipleDelimsAsOne',1);
fclose(fid);

pos_node = [pos_node_temp_1{1,1} pos_node_temp_1{1,2} pos_node_temp_1{1,3} pos_node_temp_1{1,4}];

for i = 1:2:length(pos_node)
    p = find(abs(RailNodes_num(:,kk)-pos_node(i,1))<1e-5);
    RailNodes_RCR = [RailNodes_RCR; RailNodes(p,kk)];
    RailNodes_bools(p,kk) = 1;
end

% Beam properities
fid = fopen('RailSectionSI_RCR.inp');
beam_properities_1 = textscan(fid,'%f %f %f %f %f\n \b\n %f %f','HeaderLines',196,'Delimiter',',','CommentStyle','*BEAM');
fclose(fid);

for k = 1:1:length(RailNodes_RCR)-1
    RailNodes_RCR(k,1).Area = beam_properities_1{1,1};
    RailNodes_RCR(k,1).I11 = beam_properities_1{1,2};
    RailNodes_RCR(k,1).I12 = beam_properities_1{1,3};
    RailNodes_RCR(k,1).I22 = beam_properities_1{1,4};
    RailNodes_RCR(k,1).TorsionalConstant = beam_properities_1{1,5};
    RailNodes_RCR(k,1).YoungModulus = beam_properities_1{1,6};
    RailNodes_RCR(k,1).ShearModulus = beam_properities_1{1,7};
end

% for k = 1:1:length(RailNodes_RCR)-1
%     if ~isempty(RailNodes_RCR(k,1).Area)
%         loc = [RailNodes_RCR(k,1).location; RailNodes_RCR(k+1,1).location];
%         RailNodes_RCR(k,1).Length = sqrt((loc(2,1)-loc(1,1))^2+(loc(2,2)-loc(1,2))^2+(loc(2,3)-loc(1,3))^2);
%         RailNodes_RCR(k,1).Mass = RailNodes_RCR(k,1).Area * RailNodes_RCR(k,1).Length * Density;
%     end
% end

%% 筛选 RailNodes_num, RailNodes_pos
temp = find(RailNodes_bools==0);
RailNodes_num_v1(temp) = 0;
RailNodes_num_v1 = [RailNodesTrackExtension_num(1:end-1,1) zeros(length(RailNodesTrackExtension_num)-1,2) ...
                    RailNodesTrackExtension_num(1:end-1,2) zeros(length(RailNodesTrackExtension_num)-1,3);... 
                    RailNodes_num_v1];

for i = 1:1:length(temp)
    RailNodes_pos_v1{temp(i)} = [];
end
RailNodes_pos_v1_temp = cell(length(RailNodesTrackExtension_pos)-1,7);
RailNodes_pos_v1_temp(1:length(RailNodesTrackExtension_pos)-1,1) = RailNodesTrackExtension_pos(1:end-1,1);
RailNodes_pos_v1_temp(1:length(RailNodesTrackExtension_pos)-1,4) = RailNodesTrackExtension_pos(1:end-1,2);
RailNodes_pos_v1 = [RailNodes_pos_v1_temp; RailNodes_pos_v1];
